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
        """Provides local-first response mocks to support offline development."""
        content = "Simulated Gemini Response based on input prompt."
        
        if "fastapi" in prompt.lower() or "code" in prompt.lower():
            content = (
                "Based on prompt, here is the Gemini FastAPI code:\n"
                "```python\n"
                "from fastapi import FastAPI\n"
                "app = FastAPI(title='Gemini Axiom Service')\n"
                "```"
            )
        elif "policy" in prompt.lower() or "risk" in prompt.lower():
            content = (
                "Based on the analysis, here is the Gemini action proposal:\n"
                "```json\n"
                "{\n"
                "  \"action_type\": \"tool_call\",\n"
                "  \"tool_id\": \"refund_tool_v1\",\n"
                "  \"tool_input\": {\"amount\": 240.0},\n"
                "  \"rationale\": \"Gemini identified refund logic triggers due to customer returns criteria compliance.\",\n"
                "  \"confidence\": 0.93,\n"
                "  \"risk_self_assessment\": \"medium\"\n"
                "}\n"
                "```"
            )

        return {
            "content": content,
            "tokens_used": {
                "input": len(prompt) // 4,
                "output": len(content) // 4,
                "cost_usd": 0.0001
            },
            "model_used": f"{self.model_name}-simulated",
            "confidence_estimate": 0.91
        }
