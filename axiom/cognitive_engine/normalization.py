import re
from typing import Dict, Any

class NormalizationLayer:
    """
    Layer 3: Normalization.
    Standardizes nomenclature, mapping legacy terms (e.g. OctaMind)
    to canonical Axiom architecture terms based on the global replacement rules.
    """
    REPLACEMENTS = {
        r"\bOctaMind Cognitive Engine\b": "Axiom Cognitive Engine (ACE)",
        r"\bOctaMind Cognitive Engine\b": "Axiom Cognitive Engine (ACE)",
        r"\bOctaMind Pipeline\b": "Axiom Intelligence Pipeline",
        r"\bOctaMind Architecture\b": "Axiom Architecture",
        r"\bOctaMind OS\b": "Axiom AI Platform",
        r"\bOctaMind APIs\b": "Axiom APIs",
        r"\bOctaMind AI\b": "Axiom AI",
        r"\bOctaMind\b": "Axiom",
        r"\bAI Engineering Platform\b": "AI-Driven Inference IoT Orchestration Model",
        r"\boctamind/\b": "axiom/"
    }

    def __init__(self):
        pass

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        query = payload.get("query", "")
        normalized_query = query
        for pattern, replacement in self.REPLACEMENTS.items():
            normalized_query = re.sub(pattern, replacement, normalized_query, flags=re.IGNORECASE)
        payload["normalized_query"] = normalized_query

        # Also normalize the captured context snippets to ensure nomenclature uniformity
        context_chunks = payload.get("captured_context", [])
        for chunk in context_chunks:
            content = chunk.get("content", "")
            for pattern, replacement in self.REPLACEMENTS.items():
                content = re.sub(pattern, replacement, content, flags=re.IGNORECASE)
            chunk["content"] = content
        
        payload["captured_context"] = context_chunks
        return payload
