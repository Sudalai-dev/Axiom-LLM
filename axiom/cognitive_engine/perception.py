import re
from typing import Dict, Any

class PerceptionLayer:
    """
    Layer 1: Perception.
    Parses and validates the incoming query, identifies the project scope,
    detects the target intent, and runs safety / security boundary checks.
    """
    def __init__(self):
        pass

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        query = payload.get("query", "").strip()
        if not query:
            raise ValueError("Empty query received in Perception Layer.")

        # Basic security/injection checks
        if any(bad_phrase in query.lower() for bad_phrase in ["drop table", "delete from", "format c:"]):
            payload["security_alert"] = True
            payload["status"] = "REJECTED"
            payload["rejection_reason"] = "Security violation detected in input query."
            return payload

        # Simple keyword-based intent classification
        intent = "GeneralQ&A"
        if re.search(r"\b(code|function|class|fastapi|python|generate|write)\b", query, re.I):
            intent = "CodeGen"
        elif re.search(r"\b(architecture|design|db|schema|structure|layers|blueprint)\b", query, re.I):
            intent = "ArchitectureReview"

        payload["intent"] = intent
        payload["status"] = "PROCESSED"
        return payload
