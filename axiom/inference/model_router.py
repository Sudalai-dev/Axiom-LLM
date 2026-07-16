"""
OCIF Model Router — Layer 6.

Handles model provider routing and availability checks. Implements "auto" routing
based on task type, token cost constraints, and fallback state (per Doc 10 Section 6).

Traces to:
  - Document 10 (API Specification) Section 6: Cognition API
  - Document 18 (Deployment Guide) Section 7: Fallback patterns (LLM provider outage)
"""

import logging
import time
from typing import Dict, Any, Optional, Tuple



from core.config import settings
from core.models.base import LLMProvider
from inference.providers.base import BaseLLMProvider
from inference.providers.openai_provider import OpenAIProvider
from inference.providers.claude_provider import ClaudeProvider
from inference.providers.gemini_provider import GeminiProvider
from inference.providers.llama_provider import LlamaProvider
from inference.providers.opencode_provider import OpenCodeProvider

logger = logging.getLogger("AxiomModelRouter")

# How long a provider stays circuit-broken after a reported failure before it
# is retried. Previously the outage list was never consulted with an expiry, so
# a provider marked failed stayed "offline" for the life of the process (and
# report_failure was never actually called anywhere).
_CIRCUIT_COOLDOWN_SECONDS = 300


class ModelRouter:
    """
    Routes requests to correct model providers and manages active fallbacks.
    """

    def __init__(self) -> None:
        self.providers: Dict[LLMProvider, BaseLLMProvider] = {
            LLMProvider.OPENAI: OpenAIProvider(),
            LLMProvider.CLAUDE: ClaudeProvider(),
            LLMProvider.GEMINI: GeminiProvider(),
            LLMProvider.LLAMA: LlamaProvider(),
            LLMProvider.OPENCODE: OpenCodeProvider(),
        }
        # In-memory track of failed providers for circuit-breaking:
        # provider -> unix timestamp when it was marked offline.
        self.failed_providers: Dict[LLMProvider, float] = {}

    def _is_circuit_open(self, provider: LLMProvider) -> bool:
        """True if the provider is still within its failure cooldown window."""
        marked_at = self.failed_providers.get(provider)
        if marked_at is None:
            return False
        if (time.time() - marked_at) >= _CIRCUIT_COOLDOWN_SECONDS:
            # Cooldown elapsed — clear it and let the provider be tried again.
            self.failed_providers.pop(provider, None)
            return False
        return True

    def get_provider(
        self,
        selected_provider: LLMProvider,
        intent: str,
        force: bool = False,
    ) -> Tuple[LLMProvider, BaseLLMProvider]:
        """
        Resolves the appropriate provider to call.

        ``force=True`` pins the exact provider (used by the freemium gate to
        route free-tier traffic to OpenCode) and skips 'auto' routing, but
        still honors the circuit breaker so a downed provider falls back.
        """
        if not force and selected_provider == LLMProvider.AUTO:
            selected_provider = self._resolve_auto_routing(intent)

        # Honor the circuit breaker (with cooldown expiry).
        if self._is_circuit_open(selected_provider):
            logger.warning(
                f"Provider '{selected_provider}' is in failure cooldown. Activating fallback."
            )
            selected_provider = self._get_fallback_provider(selected_provider)

        provider_impl = self.providers.get(selected_provider)
        if not provider_impl:
            selected_provider = LLMProvider.LLAMA
            provider_impl = self.providers[LLMProvider.LLAMA]

        return selected_provider, provider_impl

    def report_failure(self, provider: LLMProvider) -> None:
        """Flags a provider as offline (sets cooldown timestamp)."""
        self.failed_providers[provider] = time.time()
        logger.error(f"Provider '{provider}' reported failure. Circuit opened for {_CIRCUIT_COOLDOWN_SECONDS}s.")

    def _resolve_auto_routing(self, intent: str) -> LLMProvider:
        """
        Routes based on semantic intent mappings.
        - CodeGen -> Claude (highest code-gen accuracy)
        - ArchitectureReview -> OpenAI (strong design capabilities)
        - SystemAdmin/GeneralQ&A -> Gemini (high efficiency)
        """
        if intent == "CodeGen":
            return LLMProvider.CLAUDE
        elif intent == "ArchitectureReview":
            return LLMProvider.OPENAI
        else:
            # Default general routing
            return LLMProvider.GEMINI

    def _get_fallback_provider(self, primary: LLMProvider) -> LLMProvider:
        """Determines the secondary fallback provider order (Doc 18 Section 7)."""
        fallback_map = {
            LLMProvider.CLAUDE: LLMProvider.OPENAI,
            LLMProvider.OPENAI: LLMProvider.GEMINI,
            LLMProvider.GEMINI: LLMProvider.LLAMA,
            LLMProvider.LLAMA: LLMProvider.OPENAI  # loop fallback
        }
        return fallback_map.get(primary, LLMProvider.LLAMA)
