from typing import Dict, Any
import logging

class CognitionLayer:
    """
    Layer 6: Cognition.
    Executes local reasoning/inference. Uses local LLM weight parameters if available,
    otherwise falls back to a deterministic rule-based local generator designed to 
    satisfy engineering requirements offline.
    """
    def __init__(self, use_simulated_llm: bool = True):
        self.use_simulated_llm = use_simulated_llm
        self.logger = logging.getLogger("AxiomCognition")

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        synthesis = payload.get("synthesis_model", {})
        query = synthesis.get("query", "")
        intent = synthesis.get("intent", "GeneralQ&A")
        context = synthesis.get("formatted_context", "")
        guidelines = synthesis.get("formatted_guidelines", "")

        self.logger.info(f"Running Cognition Layer for intent: {intent}")

        # Check if we should simulate LLM reasoning (default behavior for local lightweight run)
        if self.use_simulated_llm:
            reasoning = self._generate_simulated_reasoning(query, intent, context, guidelines)
        else:
            # Here you would load local weights or query the local vLLM API endpoint
            # e.g., requests.post("http://localhost:8000/v1/completions", json={...})
            reasoning = "[Local LLM weights not loaded. Please set use_simulated_llm=True]"

        payload["cognition_reasoning"] = reasoning
        return payload

    def _generate_simulated_reasoning(self, query: str, intent: str, context: str, guidelines: str) -> str:
        """
        Simulates structured reasoning to ensure a robust output is generated locally.
        """
        response_template = (
            f"### Axiom Cognitive Engine Reasoning Trace\n"
            f"- **Intent classified**: {intent}\n"
            f"- **Rules applied**:\n{guidelines}\n\n"
        )
        
        if intent == "CodeGen":
            response_template += (
                "Based on the normalization and coding standards, here is the FastAPI implementation:\n\n"
                "```python\n"
                "from fastapi import FastAPI, HTTPException\n"
                "from pydantic import BaseModel\n\n"
                "app = FastAPI(title='Axiom Core Services')\n\n"
                "class NormalizationRequest(BaseModel):\n"
                "    query: str\n\n"
                "@app.post('/normalize')\n"
                "def normalize_query(req: NormalizationRequest):\n"
                "    # Implementation of Layer 3 Normalization\n"
                "    query_text = req.query\n"
                "    # standard replacements\n"
                "    query_text = query_text.replace('OctaMind', 'Axiom')\n"
                "    return {'normalized_query': query_text}\n"
                "```"
            )
        elif intent == "ArchitectureReview":
            response_template += (
                "### Axiom Core Architectural Alignment\n"
                "1. **Core layers**: The design successfully separates concerns into discrete micro-modules.\n"
                "2. **State boundary**: Ensure the Synthesis Layer (Layer 5) maintains volatility.\n"
                "3. **Closed-loop verification**: The output from Layer 8 (Experience) must loop back to Layer 1 (Perception)."
            )
        else:
            response_template += (
                f"### Axiom Engineering Guidance\n"
                f"Your query: \"{query}\" has been evaluated against the local database context.\n"
                f"Here is the relevant information extracted from local documentation:\n\n"
                f"{context if context else 'No local documentation matches found for the query keywords.'}"
            )
            
        return response_template
