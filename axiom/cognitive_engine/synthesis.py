from typing import Dict, Any

class SynthesisLayer:
    """
    Layer 5: Synthesis.
    Composes a unified engineering context payload, assembling the query,
    retrieved snippets, standard naming mappings, and guidelines into a single schema.
    """
    def __init__(self):
        pass

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        normalized_query = payload.get("normalized_query", "")
        intent = payload.get("intent", "GeneralQ&A")
        context_chunks = payload.get("captured_context", [])
        guidelines = payload.get("enriched_guidelines", [])

        # Construct the final prompt representation that represents this state
        context_str = "\n".join(
            f"--- Context Source: {c['source']} (Line {c['line_number']}) ---\n{c['content']}"
            for c in context_chunks
        )

        guidelines_str = "\n".join(f"- {g}" for g in guidelines)

        synthesis_model = {
            "query": normalized_query,
            "intent": intent,
            "formatted_context": context_str,
            "formatted_guidelines": guidelines_str,
            "session_id": payload.get("session_id", "default-session")
        }

        payload["synthesis_model"] = synthesis_model
        return payload
