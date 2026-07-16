"""
Shared LLM inference boundary.

Moved out of ocif/engines/reasoning.py so both the Reasoning Engine (final
solution authoring) and the Project Understanding classifier (upstream
project/industry classification) share one ModelRouter instance — and
therefore one consistent view of provider circuit-breaking — instead of
each engine building its own. This is a deliberate, narrow exception to the
platform's "LLM inference happens only inside reasoning.py" convention:
genuine classification across unbounded industries requires real reasoning,
not another fixed keyword list.
"""

import logging
from typing import Any, Dict, Optional

from core.config import settings

logger = logging.getLogger("AxiomOCIF.InferenceAdapter")


class InferenceAdapter:
    """
    Neutral inference interface. Wraps the platform ModelRouter; no engine
    logic outside this class may depend on a provider's API idiosyncrasies.
    """

    def __init__(self) -> None:
        self._router = None

    def _get_router(self):
        if self._router is None:
            from inference.model_router import ModelRouter
            self._router = ModelRouter()
        return self._router

    async def complete(
        self,
        prompt: str,
        intent: str,
        provider_override: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Returns {"content": str, "model_used": str, "provider": str,
        "tokens_used": {...}} or None when no usable (non-simulated) provider
        responds — in which case the caller falls back to the deterministic
        synthesizer.

        ``provider_override`` pins the provider for this call regardless of the
        configured default routing. The freemium gate passes ``"opencode"`` for
        free-tier users so their agent traffic is served by the local OpenCode
        runtime; paid/privileged users pass ``None`` and use the platform's
        configured cloud provider.

        On a provider error the failing provider is circuit-broken and one
        fallback provider is attempted before giving up (bounded retry).
        """
        from core.models.base import LLMProvider

        forced = False
        if provider_override:
            try:
                provider_enum = LLMProvider(provider_override.lower())
                forced = True
            except ValueError:
                logger.warning(f"Unknown provider_override '{provider_override}'; using default routing.")
                provider_enum = self._default_provider_enum()
        else:
            provider_enum = self._default_provider_enum()

        router = self._get_router()
        attempts = 0
        last_provider: Optional[LLMProvider] = None
        while attempts < 2:
            attempts += 1
            name, impl = router.get_provider(provider_enum, intent, force=forced and attempts == 1)
            if name == last_provider:
                break  # no distinct fallback available
            last_provider = name
            try:
                payload = await impl.generate(
                    prompt=prompt,
                    max_tokens=settings.llm.default_max_tokens,
                    temperature=settings.llm.default_temperature,
                )
            except Exception as exc:
                logger.warning(f"Provider '{name.value}' failed (attempt {attempts}): {exc}")
                router.report_failure(name)
                # Retry via the fallback chain (no longer forced).
                forced = False
                provider_enum = LLMProvider.AUTO
                continue

            model_used = str(payload.get("model_used", ""))
            if model_used.endswith("-simulated"):
                # Offline mock cannot author real solutions — synthesize instead.
                return None
            return {
                "content": payload.get("content", ""),
                "model_used": model_used,
                "provider": name.value,
                "tokens_used": payload.get("tokens_used", {}),
            }

        return None

    @staticmethod
    def _default_provider_enum():
        from core.models.base import LLMProvider
        try:
            return LLMProvider(settings.llm.default_provider.lower())
        except ValueError:
            return LLMProvider.AUTO
