"""
OCIF OpenAI Provider Adapter — Layer 6.

Integrates with OpenAI Chat Completion API. Falls back to a local-first
simulation engine if the API key is not configured.

Traces to:
  - Document 10 (API Specification) Section 6: Cognition API
  - Document 12 (Prompt Engineering Guide) Section 8: Provider-Specific Adaptation
"""

import logging
from typing import Dict, Any

from axiom.core.config import settings
from axiom.layer6_cognition.providers.base import BaseLLMProvider

logger = logging.getLogger("AxiomOpenAIProvider")


class OpenAIProvider(BaseLLMProvider):
    """
    Adapter for OpenAI models (GPT-4o, GPT-3.5, etc.).
    """

    def __init__(self, model_name: str = "gpt-4o") -> None:
        super().__init__(model_name)
        self.api_key = settings.llm.openai_api_key

    async def generate(
        self, 
        prompt: str, 
        max_tokens: int, 
        temperature: float
    ) -> Dict[str, Any]:
        logger.debug(f"OpenAI generation request. Model: {self.model_name}")

        if not self.api_key:
            # Fallback to local simulation when keys are not configured
            logger.info("OpenAI API key not configured. Emulating completion locally.")
            return self._simulate_completion(prompt)

        try:
            import httpx
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            async with httpx.AsyncClient(timeout=settings.llm.timeout_seconds) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.error(f"OpenAI API returned error code {response.status_code}: {response.text}")
                    raise RuntimeError(f"OpenAI API error: {response.text}")
                    
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                prompt_tokens = data["usage"]["prompt_tokens"]
                completion_tokens = data["usage"]["completion_tokens"]
                
                # Estimate cost
                cost = (prompt_tokens * 0.005 / 1000) + (completion_tokens * 0.015 / 1000)
                
                return {
                    "content": content,
                    "tokens_used": {
                        "input": prompt_tokens,
                        "output": completion_tokens,
                        "cost_usd": cost
                    },
                    "model_used": self.model_name,
                    "confidence_estimate": 0.94
                }
        except Exception as e:
            logger.error(f"OpenAI generation failure: {e}")
            raise

    def _simulate_completion(self, prompt: str) -> Dict[str, Any]:
        return super()._simulate_completion(prompt)

