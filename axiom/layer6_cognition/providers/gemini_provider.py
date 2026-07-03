"""
OCIF Google Gemini Provider Adapter — Layer 6.

Integrates with Google Gemini Developer API. Falls back to a local-first
simulation engine if the API key is not configured.

Traces to:
  - Document 10 (API Specification) Section 6: Cognition API
  - Document 12 (Prompt Engineering Guide) Section 8: Provider-Specific Adaptation
"""

import logging
from typing import Dict, Any

from axiom.core.config import settings
from axiom.layer6_cognition.providers.base import BaseLLMProvider

logger = logging.getLogger("AxiomGeminiProvider")


class GeminiProvider(BaseLLMProvider):
    """
    Adapter for Google Gemini models (Gemini 1.5 Pro, Gemini 1.5 Flash, etc.).
    """

    def __init__(self, model_name: str = "gemini-1.5-pro") -> None:
        super().__init__(model_name)
        self.api_key = settings.llm.gemini_api_key

    async def generate(
        self, 
        prompt: str, 
        max_tokens: int, 
        temperature: float
    ) -> Dict[str, Any]:
        logger.debug(f"Gemini generation request. Model: {self.model_name}")

        if not self.api_key:
            logger.info("Gemini API key not configured. Emulating completion locally.")
            return self._simulate_completion(prompt)

        try:
            import httpx
            # Format API URL with API Key parameter
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
            headers = {
                "Content-Type": "application/json"
            }
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "maxOutputTokens": max_tokens,
                    "temperature": temperature
                }
            }
            
            async with httpx.AsyncClient(timeout=settings.llm.timeout_seconds) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.error(f"Gemini API returned error code {response.status_code}: {response.text}")
                    raise RuntimeError(f"Gemini API error: {response.text}")
                    
                data = response.json()
                content = data["candidates"][0]["content"]["parts"][0]["text"]
                
                # Gemini doesn't always expose token usage in simple payload returns,
                # so we estimate token sizes.
                prompt_tokens = len(prompt) // 4
                completion_tokens = len(content) // 4
                cost = (prompt_tokens * 0.00125 / 1000) + (completion_tokens * 0.00375 / 1000)
                
                return {
                    "content": content,
                    "tokens_used": {
                        "input": prompt_tokens,
                        "output": completion_tokens,
                        "cost_usd": cost
                    },
                    "model_used": self.model_name,
                    "confidence_estimate": 0.95
                }
        except Exception as e:
            logger.error(f"Gemini generation failure: {e}")
            raise

    def _simulate_completion(self, prompt: str) -> Dict[str, Any]:
        return super()._simulate_completion(prompt)

