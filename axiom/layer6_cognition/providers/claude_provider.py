"""
OCIF Anthropic Claude Provider Adapter — Layer 6.

Integrates with Anthropic Messages API. Falls back to a local-first
simulation engine if the API key is not configured.

Traces to:
  - Document 10 (API Specification) Section 6: Cognition API
  - Document 12 (Prompt Engineering Guide) Section 8: Provider-Specific Adaptation
"""

import logging
from typing import Dict, Any

from axiom.core.config import settings
from axiom.layer6_cognition.providers.base import BaseLLMProvider

logger = logging.getLogger("AxiomClaudeProvider")


class ClaudeProvider(BaseLLMProvider):
    """
    Adapter for Claude models (Claude 3.5 Sonnet, Claude 3 Opus, etc.).
    """

    def __init__(self, model_name: str = "claude-3-5-sonnet") -> None:
        super().__init__(model_name)
        self.api_key = settings.llm.claude_api_key

    async def generate(
        self, 
        prompt: str, 
        max_tokens: int, 
        temperature: float
    ) -> Dict[str, Any]:
        logger.debug(f"Claude generation request. Model: {self.model_name}")

        if not self.api_key:
            logger.info("Claude API key not configured. Emulating completion locally.")
            return self._simulate_completion(prompt)

        try:
            import httpx
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
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
                    "https://api.anthropic.com/v1/messages",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code != 200:
                    logger.error(f"Claude API returned error code {response.status_code}: {response.text}")
                    raise RuntimeError(f"Claude API error: {response.text}")
                    
                data = response.json()
                content = data["content"][0]["text"]
                prompt_tokens = data["usage"]["input_tokens"]
                completion_tokens = data["usage"]["output_tokens"]
                
                # Estimate cost
                cost = (prompt_tokens * 0.003 / 1000) + (completion_tokens * 0.015 / 1000)
                
                return {
                    "content": content,
                    "tokens_used": {
                        "input": prompt_tokens,
                        "output": completion_tokens,
                        "cost_usd": cost
                    },
                    "model_used": self.model_name,
                    "confidence_estimate": 0.96
                }
        except Exception as e:
            logger.error(f"Claude generation failure: {e}")
            raise

    def _simulate_completion(self, prompt: str) -> Dict[str, Any]:
        """Provides local-first response mocks to support offline development."""
        content = "Simulated Claude Response based on input prompt."
        
        if "fastapi" in prompt.lower() or "code" in prompt.lower():
            content = (
                "Based on prompt, here is the Claude FastAPI code:\n"
                "```python\n"
                "from fastapi import FastAPI\n"
                "app = FastAPI(title='Claude Axiom Service')\n"
                "```"
            )
        elif "policy" in prompt.lower() or "risk" in prompt.lower():
            content = (
                "Based on the analysis, here is the Claude action proposal:\n"
                "```json\n"
                "{\n"
                "  \"action_type\": \"tool_call\",\n"
                "  \"tool_id\": \"refund_tool_v1\",\n"
                "  \"tool_input\": {\"amount\": 240.0},\n"
                "  \"rationale\": \"Claude proposed refund based on returns policy eligibility checking.\",\n"
                "  \"confidence\": 0.95,\n"
                "  \"risk_self_assessment\": \"medium\"\n"
                "}\n"
                "```"
            )

        return {
            "content": content,
            "tokens_used": {
                "input": len(prompt) // 4,
                "output": len(content) // 4,
                "cost_usd": 0.0003
            },
            "model_used": f"{self.model_name}-simulated",
            "confidence_estimate": 0.92
        }
