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

from axiom.core.config import settings
from axiom.layer6_cognition.providers.base import BaseLLMProvider

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
        """Provides local-first response mocks to support offline development."""
        content = "Simulated Local Llama Response based on input prompt."
        
        if "fastapi" in prompt.lower() or "code" in prompt.lower():
            content = (
                "Based on prompt, here is the Local Llama FastAPI code:\n"
                "```python\n"
                "from fastapi import FastAPI\n"
                "app = FastAPI(title='Local Llama Service')\n"
                "```"
            )
        elif "policy" in prompt.lower() or "risk" in prompt.lower():
            content = (
                "Based on the analysis, here is the Llama action proposal:\n"
                "```json\n"
                "{\n"
                "  \"action_type\": \"tool_call\",\n"
                "  \"tool_id\": \"refund_tool_v1\",\n"
                "  \"tool_input\": {\"amount\": 240.0},\n"
                "  \"rationale\": \"Local Llama verified refund meets rules eligibility conditions.\",\n"
                "  \"confidence\": 0.92,\n"
                "  \"risk_self_assessment\": \"medium\"\n"
                "}\n"
                "```"
            )

        return {
            "content": content,
            "tokens_used": {
                "input": len(prompt) // 4,
                "output": len(content) // 4,
                "cost_usd": 0.0
            },
            "model_used": f"{self.model_name}-simulated",
            "confidence_estimate": 0.90
        }
