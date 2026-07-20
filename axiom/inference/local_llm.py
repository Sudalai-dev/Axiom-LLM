"""
Local LLM client — self-hosted, no external/cloud provider.

Talks to a locally running Ollama (native ``/api/chat``) so AXIOM can add
dynamic prose and a visible reasoning ("thinking") stream on top of the
deterministic SolutionSynthesizer. Every method FAILS SOFT: on any error
(disabled, unreachable, model not pulled, timeout, malformed JSON) it returns
``None`` and the caller keeps the guaranteed deterministic output — the
platform never degrades to a broken response.

Stdlib-only (``urllib``) so it adds no dependency and nothing here reaches any
cloud service; the only network call is to the operator's own machine.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.request
from typing import Any, Dict, Optional

from core.config import LLMConfig

logger = logging.getLogger("AxiomOCIF.LocalLLM")

# LLM enrichment only replaces NARRATIVE prose; structured fields (tech stack,
# diagrams, ER, roadmap, risks) always stay deterministic. A returned section
# shorter than this is treated as junk and the deterministic text is kept.
_MIN_SECTION_LEN = 40
_MIN_THINKING_LEN = 20
# The model-presence probe is a cheap liveness check; keep its timeout short so
# an unreachable endpoint fails fast to the deterministic path (never the full
# generation timeout).
_AVAILABILITY_PROBE_TIMEOUT_SECONDS = 5


class LocalLLMClient:
    """Thin, fail-soft client for a local Ollama server."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self._availability: Optional[bool] = None  # cached per instance

    def available(self) -> bool:
        """True only if enabled AND the configured model is actually pulled.
        Cached so we probe Ollama at most once per client instance."""
        if not self.config.enabled:
            return False
        if self._availability is None:
            self._availability = self._check_model_present()
        return self._availability

    def _check_model_present(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.config.base_url}/api/tags", method="GET")
            probe_timeout = min(_AVAILABILITY_PROBE_TIMEOUT_SECONDS, self.config.timeout_seconds)
            with urllib.request.urlopen(req, timeout=probe_timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            names = [m.get("name", "") for m in data.get("models", [])]
            want = self.config.model
            present = any(n == want or n.split(":")[0] == want.split(":")[0] for n in names)
            if not present:
                logger.warning(
                    "Local LLM model %r not pulled (Ollama has: %s). Run: ollama pull %s",
                    want, names or "nothing", want,
                )
            return present
        except Exception as exc:  # noqa: BLE001 — fail soft into deterministic output
            logger.info(
                "Local LLM not reachable at %s (%s); using deterministic output.",
                self.config.base_url, exc,
            )
            return False

    def chat(
        self, system: str, user: str, *,
        temperature: Optional[float] = None, max_tokens: Optional[int] = None,
        seed: Optional[int] = None,
    ) -> Optional[str]:
        """One non-streaming chat turn. Returns the assistant text, or None.
        ``seed`` (when set) makes generation reproducible — used for diagram
        structure so the same request yields the same diagram."""
        if not self.available():
            return None
        options = {
            "temperature": self.config.temperature if temperature is None else temperature,
            "num_predict": self.config.max_tokens if max_tokens is None else max_tokens,
            # Enlarge the context window so AXIOM's long grounding prompt
            # isn't truncated by Ollama's 2048-token default.
            "num_ctx": self.config.context_tokens,
        }
        if seed is not None:
            options["seed"] = seed
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "options": options,
        }
        try:
            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                f"{self.config.base_url}/api/chat", data=body,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = (data.get("message") or {}).get("content", "") or ""
            return content.strip() or None
        except Exception as exc:  # noqa: BLE001 — fail soft
            logger.warning("Local LLM chat failed (%s); using deterministic output.", exc)
            return None

    def chat_json(self, system: str, user: str, **kw: Any) -> Optional[Dict[str, Any]]:
        """chat() expecting a JSON object, tolerant of code fences / stray prose."""
        raw = self.chat(system, user, **kw)
        return _extract_json_object(raw) if raw else None


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    t = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if fence:
        t = fence.group(1).strip()
    start, end = t.find("{"), t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        obj = json.loads(t[start:end + 1])
        return obj if isinstance(obj, dict) else None
    except Exception:  # noqa: BLE001
        return None


_SYSTEM_PROMPT = (
    "You are AXIOM's reasoning core: a panel of senior engineering experts. "
    "You are given a deterministic engineering solution draft and must (1) briefly "
    "show your reasoning and (2) rewrite two narrative sections to be sharper, more "
    "specific, and tailored to THIS request. Hard rules: never invent technologies, "
    "standards, or components beyond those provided; keep every claim grounded in the "
    "given context; be concise and professional; never mention that you are an AI, a "
    "model, or a 'panel'. Return ONLY a single JSON object, no prose around it, with "
    'exactly these string keys: "thinking", "executive_summary", "recommended_solution".'
)


def draft_reasoning_and_prose(
    client: LocalLLMClient,
    *,
    subject: str,
    entities: list,
    domains: list,
    industry: str,
    standards: list,
    rules: list,
    base_summary: str,
    base_recommendation: str,
) -> Optional[Dict[str, str]]:
    """Ask the local model for a reasoning trace + two enhanced narrative
    sections, grounded in the deterministic draft. Returns a dict with
    ``thinking`` / ``executive_summary`` / ``recommended_solution`` (only the
    keys that came back valid), or None if the model is unavailable / unusable.
    Structured content (diagrams, stack, ER, roadmap, risks) is NEVER touched
    here — the caller keeps those from the deterministic document."""
    user = (
        f"REQUEST: {subject}\n"
        f"DOMAINS: {', '.join(domains) or 'general software'}\n"
        f"INDUSTRY: {industry}\n"
        f"KEY ENTITIES (only these; do not invent more): {', '.join(entities) or 'none extracted'}\n"
        f"APPLICABLE STANDARDS (only these): {', '.join(standards) or 'none'}\n"
        f"ENGINEERING RULES THAT FIRED: {', '.join(rules) or 'none'}\n\n"
        f"DETERMINISTIC EXECUTIVE SUMMARY (improve, keep facts):\n{base_summary}\n\n"
        f"DETERMINISTIC RECOMMENDED SOLUTION (improve, keep facts):\n{base_recommendation}\n\n"
        "Now return the JSON object."
    )
    obj = client.chat_json(_SYSTEM_PROMPT, user)
    if not obj:
        return None

    out: Dict[str, str] = {}
    thinking = obj.get("thinking")
    if isinstance(thinking, str) and len(thinking.strip()) >= _MIN_THINKING_LEN:
        out["thinking"] = thinking.strip()
    for key in ("executive_summary", "recommended_solution"):
        val = obj.get(key)
        if isinstance(val, str) and len(val.strip()) >= _MIN_SECTION_LEN:
            out[key] = val.strip()
    return out or None


# Reproducible seed for diagram-structure generation (recorded in the trace).
DIAGRAM_STRUCTURE_SEED = 7

_DIAGRAM_SYSTEM_PROMPT = (
    "You are AXIOM's diagram engine. Given a set of typed entities and typed "
    "relationships for an engineering request, and one OCIF layer with a diagram "
    "intent, output ONLY the diagram STRUCTURE as a single JSON object:\n"
    '{"nodes":[{"id":"<name>","type":"<entity type>"}],'
    '"edges":[{"source":"<name>","target":"<name>","type":"<relationship>"}]}\n'
    "Hard rules: use ONLY the provided entity names (and, if needed, the listed "
    "allowed primitives) as node ids — never invent names. Model how the entities "
    "are handled AT THIS LAYER per the intent. Keep it focused (3-8 nodes). Output "
    "the JSON object only, no prose, no code fences."
)


def propose_diagram_structure(
    client: LocalLLMClient,
    *,
    layer: str,
    intent: str,
    diagram_type: str,
    typed_entities: list,
    relationships: list,
    allowed_primitives: list,
) -> Optional[Dict[str, Any]]:
    """Ask the local model to propose diagram structure (nodes + typed edges) for
    one layer, grounded on the facts packet. Returns the parsed dict (with
    ``nodes``/``edges`` lists) or None. The caller enforces grounding + emits
    mermaid deterministically — this only proposes structure."""
    ents = ", ".join(f'{e.get("name")}({e.get("type")})' for e in (typed_entities or [])) or "none"
    rels = ", ".join(
        f'{r.get("source")} -{r.get("type")}-> {r.get("target")}' for r in (relationships or [])
    ) or "none"
    prims = ", ".join(allowed_primitives or []) or "none"
    user = (
        f"LAYER: {layer}\nDIAGRAM INTENT: {intent}\nDIAGRAM TYPE: {diagram_type}\n"
        f"ENTITIES (name(type) — use these as node ids): {ents}\n"
        f"RELATIONSHIPS: {rels}\n"
        f"ALLOWED PRIMITIVES (only if needed): {prims}\n\n"
        "Return the JSON structure now."
    )
    obj = client.chat_json(_DIAGRAM_SYSTEM_PROMPT, user, temperature=0.1, seed=DIAGRAM_STRUCTURE_SEED)
    if not isinstance(obj, dict):
        return None
    if not isinstance(obj.get("nodes"), list) or not isinstance(obj.get("edges"), list):
        return None
    return obj
