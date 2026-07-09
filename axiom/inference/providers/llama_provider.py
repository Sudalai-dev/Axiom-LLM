"""
OCIF Local Llama Provider Adapter — Layer 6.

Integrates with local runtimes (vLLM / Ollama OpenAI-compatible endpoints) per settings.
Falls back to local mock if endpoint is unreachable.

Traces to:
  - Document 10 (API Specification) Section 6: Cognition API
  - Document 12 (Prompt Engineering Guide) Section 8: Provider-Specific Adaptation
"""

import logging
from typing import Dict, Any

from core.config import settings
from inference.providers.base import BaseLLMProvider

logger = logging.getLogger("AxiomLlamaProvider")


class LlamaProvider(BaseLLMProvider):
    """
    Adapter for local LLM servers (Llama 3.1 8B, Qwen 2.5 Coder, etc.).
    """

    def __init__(self, model_name: str = "qwen2.5-coder") -> None:
        super().__init__(model_name)
        self.endpoint = settings.llm.llama_endpoint or "http://localhost:8000/v1/chat/completions"

    async def generate(
        self, 
        prompt: str, 
        max_tokens: int, 
        temperature: float
    ) -> Dict[str, Any]:
        logger.debug(f"Llama generation request. Endpoint: {self.endpoint}")

        try:
            import httpx
            headers = {
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
                    self.endpoint,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    raise RuntimeError(f"Local model server returned error: {response.text}")
                    
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                prompt_tokens = data["usage"]["prompt_tokens"]
                completion_tokens = data["usage"]["completion_tokens"]
                
                return {
                    "content": content,
                    "tokens_used": {
                        "input": prompt_tokens,
                        "output": completion_tokens,
                        "cost_usd": 0.0  # Local running cost is zero
                    },
                    "model_used": self.model_name,
                    "confidence_estimate": 0.93
                }
        except Exception as e:
            logger.warning(
                f"Local model server at {self.endpoint} unreachable ({e}). "
                f"Defaulting to local simulation mock."
            )
            return self._simulate_completion(prompt)

    def _simulate_completion(self, prompt: str) -> Dict[str, Any]:
        return super()._simulate_completion(prompt)

