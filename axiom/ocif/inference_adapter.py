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

    async def complete(self, prompt: str, intent: str) -> Optional[Dict[str, Any]]:
        """
        Returns {"content": str, "model_used": str} or None when no usable
        (non-simulated) provider responds.
        """
        from core.models.base import LLMProvider
        try:
            provider_enum = LLMProvider(settings.llm.default_provider.lower())
        except ValueError:
            provider_enum = LLMProvider.AUTO

        try:
            name, impl = self._get_router().get_provider(provider_enum, intent)
            payload = await impl.generate(
                prompt=prompt,
                max_tokens=settings.llm.default_max_tokens,
                temperature=settings.llm.default_temperature,
            )
            model_used = str(payload.get("model_used", ""))
            if model_used.endswith("-simulated"):
                # Offline mock cannot author real solutions — synthesize instead.
                return None
            return {"content": payload.get("content", ""), "model_used": model_used,
                    "provider": name.value}
        except Exception as exc:
            logger.warning(f"LLM inference unavailable, using synthesizer: {exc}")
            return None
