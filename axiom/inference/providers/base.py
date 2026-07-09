"""
OCIF LLM Provider Base Interface — Layer 6.

Defines the abstract interface that all model provider adapters must implement,
ensuring consistent response structures and token statistics tracking.

Traces to:
  - Document 12 (Prompt Engineering Guide) Section 8: Provider-Specific Adaptation
  - Document 10 (API Specification) Section 6: Cognition API
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseLLMProvider(ABC):
    """
    Abstract Base Class for LLM Provider adapters.
    """

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    @abstractmethod
    async def generate(
        self, 
        prompt: str, 
        max_tokens: int, 
        temperature: float
    ) -> Dict[str, Any]:
        """
        Executes a completion generation request.
        
        Returns a dictionary structure:
        {
            "content": str,
            "tokens_used": {
                "input": int,
                "output": int,
                "cost_usd": float
            },
            "model_used": str,
            "confidence_estimate": float
        }
        """
        pass

    def _simulate_completion(self, prompt: str) -> Dict[str, Any]:
        """Provides local-first response mocks to support offline development."""
        import re
        import json

        # Standard simulated response text based on prompt content
        # 1. Check if the prompt requests JSON formatting instructions for GeneralQ&A / ArchitectureReview
        is_json = "json structure" in prompt.lower()
        
        # 2. Extract any retrieved knowledge chunks printed in the prompt
        # PromptBuilder templates print chunks as:
        # --- Chunk Citation ID: {chunk_id} (Source: {title}, Ref: {ref}) ---
        # {text}
        chunks = re.findall(
            r"--- Chunk Citation ID:\s*([A-Za-z0-9_\-]+)\s*\(Source:\s*([^,]+),\s*Ref:\s*([^\)]+)\)\s*---\n(.*?)\n\n",
            prompt,
            re.DOTALL
        )

        if chunks:
            # We have grounded chunks! Use the first chunk to simulate a grounded answer
            chunk_id, source, ref, text = chunks[0]
            clean_text = text.strip().replace("\n", " ")
            answer = f"According to {source} ({ref}): {clean_text[:400]}"
            if len(clean_text) > 400:
                answer += "..."
            citations = [chunk_id]
            grounded = True
        else:
            # No chunks
            answer = "No grounding found; I have no information to answer this query."
            citations = []
            grounded = False

        if is_json:
            content_dict = {
                "answer": answer,
                "confidence": 0.95 if grounded else 0.0,
                "citations": citations,
                "grounded": grounded
            }
            content = json.dumps(content_dict, indent=2)
        else:
            # If the query is asking for code/fastapi, we can keep the custom mock code block
            if "fastapi" in prompt.lower() or "code" in prompt.lower():
                content = (
                    f"Based on your request, here is the simulated implementation code:\n"
                    "```python\n"
                    "from fastapi import FastAPI\n"
                    "app = FastAPI(title='Axiom Simulated Service')\n"
                    "```"
                )
            elif "policy" in prompt.lower() or "risk" in prompt.lower():
                content = (
                    "```json\n"
                    "{\n"
                    "  \"action_type\": \"tool_call\",\n"
                    "  \"tool_id\": \"refund_tool_v1\",\n"
                    "  \"tool_input\": {\"amount\": 240.0},\n"
                    "  \"rationale\": \"Simulated action proposal matching rules criteria.\",\n"
                    "  \"confidence\": 0.92,\n"
                    "  \"risk_self_assessment\": \"medium\"\n"
                    "}\n"
                    "```"
                )
            else:
                content = answer

        # Calculate tokens
        input_tokens = len(prompt) // 4
        output_tokens = len(content) // 4
        cost = 0.0001 if "openai" in self.__class__.__name__.lower() else 0.0

        return {
            "content": content,
            "tokens_used": {
                "input": input_tokens,
                "output": output_tokens,
                "cost_usd": cost
            },
            "model_used": f"{self.model_name}-simulated",
            "confidence_estimate": 0.91 if grounded else 0.5
        }

