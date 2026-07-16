"""OpenCode Provider Adapter — free-tier agent runtime.

Serves the freemium *free plan*: instead of a paid cloud LLM, free users' agent
calls are answered by a locally-running OpenCode server
(https://opencode.ai) using one of its free models (the ``opencode/*-free``
family). The operator starts the runtime once with::

    opencode serve --port 4096

and AXIOM talks to its HTTP API (verified contract: create a session, submit a
prompt, wait for the turn to finish, then read the assistant message's text
parts).

Graceful degradation is the contract here: if the OpenCode server is not
running or anything goes wrong, this adapter returns a ``*-simulated`` payload,
which :class:`ocif.inference_adapter.InferenceAdapter` treats as "no live
provider" and falls back to the deterministic ``SolutionSynthesizer`` — so a
free user always gets a complete, valid solution even with OpenCode offline.

Traces to:
  - Freemium plan: free agents via OpenCode, paid via platform/user keys.
  - Document 10 (API Specification) Section 6: Cognition API (provider contract)
"""

import logging
from typing import Any, Dict, Optional

from core.config import settings
from inference.providers.base import BaseLLMProvider

logger = logging.getLogger("AxiomOpenCodeProvider")

# A sensible free default; overridable via OCIF_OPENCODE_MODEL. Format:
# "<providerID>/<modelID>" (OpenCode's own free tier lives under provider
# "opencode").
_DEFAULT_MODEL = "opencode/deepseek-v4-flash-free"


class OpenCodeProvider(BaseLLMProvider):
    """Adapter for the local OpenCode headless server (free-tier agents)."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        super().__init__(model_name or settings.entitlement.opencode_model or _DEFAULT_MODEL)
        self.base_url = settings.entitlement.opencode_url.rstrip("/")
        self.timeout = settings.entitlement.opencode_timeout_seconds
        self.enabled = settings.entitlement.opencode_enabled

    def _model_ref(self) -> Dict[str, str]:
        """Splits ``provider/id`` into OpenCode's ``{providerID, id}`` shape."""
        if "/" in self.model_name:
            provider_id, _, model_id = self.model_name.partition("/")
        else:
            provider_id, model_id = "opencode", self.model_name
        return {"providerID": provider_id, "id": model_id}

    async def generate(self, prompt: str, max_tokens: int, temperature: float) -> Dict[str, Any]:
        if not self.enabled:
            logger.info("OpenCode provider disabled; simulating completion.")
            return self._simulate_completion(prompt)
        try:
            return await self._generate_via_server(prompt)
        except Exception as exc:
            # Never propagate — degrade to the synthesizer path.
            logger.warning(f"OpenCode generation unavailable ({exc}); degrading to synthesizer.")
            return self._simulate_completion(prompt)

    async def _generate_via_server(self, prompt: str) -> Dict[str, Any]:
        import httpx

        model = self._model_ref()
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            # Fail fast if the server isn't up, so we degrade quickly.
            health = await client.get("/api/health", timeout=5.0)
            health.raise_for_status()

            session = await client.post("/api/session", json={"model": model})
            session.raise_for_status()
            session_id = session.json()["data"]["id"]

            prompt_resp = await client.post(
                f"/api/session/{session_id}/prompt",
                json={"prompt": {"text": prompt}, "model": model},
            )
            prompt_resp.raise_for_status()

            # Block until the assistant turn completes (the prompt call is async).
            await client.post(f"/api/session/{session_id}/wait")

            messages = await client.get(
                f"/api/session/{session_id}/message",
                params={"order": "desc", "limit": 5},
            )
            messages.raise_for_status()
            return self._parse_completion(messages.json().get("data", []))

    def _parse_completion(self, messages: list) -> Dict[str, Any]:
        """Extracts the newest assistant message's text + token usage."""
        assistant = next(
            (m for m in messages if isinstance(m, dict) and m.get("type") == "assistant"),
            None,
        )
        if not assistant:
            raise RuntimeError("OpenCode returned no assistant message")

        text = "".join(
            part.get("text", "")
            for part in assistant.get("content", [])
            if isinstance(part, dict) and part.get("type") == "text"
        ).strip()
        if not text:
            raise RuntimeError("OpenCode assistant message contained no text parts")

        tokens = assistant.get("tokens") or {}
        model_ref = assistant.get("model") or {}
        model_id = model_ref.get("id", self.model_name)
        provider_id = model_ref.get("providerID", "opencode")
        return {
            "content": text,
            "tokens_used": {
                "input": int(tokens.get("input", 0) or 0),
                "output": int(tokens.get("output", 0) or 0),
                "cost_usd": float(assistant.get("cost", 0.0) or 0.0),
            },
            "model_used": f"{provider_id}/{model_id}",
            "confidence_estimate": 0.85,
        }

    def _simulate_completion(self, prompt: str) -> Dict[str, Any]:
        return super()._simulate_completion(prompt)
