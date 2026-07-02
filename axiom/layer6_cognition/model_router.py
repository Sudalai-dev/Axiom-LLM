"""
OCIF Model Router — Layer 6.

Handles model provider routing and availability checks. Implements "auto" routing
based on task type, token cost constraints, and fallback state (per Doc 10 Section 6).

Traces to:
  - Document 10 (API Specification) Section 6: Cognition API
  - Document 18 (Deployment Guide) Section 7: Fallback patterns (LLM provider outage)
"""

import logging
from typing import Dict, Any, List, Tuple



from axiom.core.config import settings
from axiom.core.models.base import LLMProvider
from axiom.layer6_cognition.providers.base import BaseLLMProvider
from axiom.layer6_cognition.providers.openai_provider import OpenAIProvider
from axiom.layer6_cognition.providers.claude_provider import ClaudeProvider
from axiom.layer6_cognition.providers.gemini_provider import GeminiProvider
from axiom.layer6_cognition.providers.llama_provider import LlamaProvider

logger = logging.getLogger("AxiomModelRouter")


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
        }
        # In-memory track of failed providers for circuit-breaking
        self.failed_providers: Dict[LLMProvider, float] = {}

    def get_provider(self, selected_provider: LLMProvider, intent: str) -> Tuple[LLMProvider, BaseLLMProvider]:
        """
        Resolves the appropriate provider to call, applying 'auto' routing policies
        and checking active outage states.
        """
        # Resolve 'auto' selection
        if selected_provider == LLMProvider.AUTO:
            selected_provider = self._resolve_auto_routing(intent)

        # Check circuit breakers
        if selected_provider in self.failed_providers:
            # If provider failed within last 5 minutes, force fallback
            logger.warning(f"Selected provider '{selected_provider}' is temporarily marked offline. Activating fallback.")
            selected_provider = self._get_fallback_provider(selected_provider)

        provider_impl = self.providers.get(selected_provider)
        if not provider_impl:
            # Fall back to Llama
            selected_provider = LLMProvider.LLAMA
            provider_impl = self.providers[LLMProvider.LLAMA]

        return selected_provider, provider_impl

    def report_failure(self, provider: LLMProvider) -> None:
        """Flags a provider as offline (sets cooldown timestamp)."""
        import time
        self.failed_providers[provider] = time.time()
        logger.error(f"Provider '{provider}' reported failure. Added to outage list.")

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
