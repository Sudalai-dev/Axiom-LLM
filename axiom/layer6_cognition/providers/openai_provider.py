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
        """Provides local-first response mocks to support offline development."""
        # Simple heuristics to generate appropriate text structures
        content = "Simulated OpenAI Response based on input prompt."
        
        # If prompt asks for code, provide FastAPI mock block
        if "fastapi" in prompt.lower() or "code" in prompt.lower():
            content = (
                "Based on prompt, here is the FastAPI implementation:\n"
                "```python\n"
                "from fastapi import FastAPI\n"
                "app = FastAPI(title='Axiom Service')\n"
                "```"
            )
        elif "policy" in prompt.lower() or "risk" in prompt.lower():
            content = (
                "Based on the analysis, here is the action proposal:\n"
                "```json\n"
                "{\n"
                "  \"action_type\": \"tool_call\",\n"
                "  \"tool_id\": \"refund_tool_v1\",\n"
                "  \"tool_input\": {\"amount\": 240.0},\n"
                "  \"rationale\": \"Customer query request refund for order #4471\",\n"
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
                "cost_usd": 0.0002
            },
            "model_used": f"{self.model_name}-simulated",
            "confidence_estimate": 0.90
        }
