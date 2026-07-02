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
