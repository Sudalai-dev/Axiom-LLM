from typing import Dict, Any

class ExperienceLayer:
    """
    Layer 8: Experience.
    Prepares the final structured presentation model for the user,
    assembling the reasoning, code blocks, diagrams, and logs into a polished display.
    """
    def __init__(self):
        pass

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        reasoning = payload.get("cognition_reasoning", "")
        artifacts = payload.get("prescribed_artifacts", [])
        
        # Build the final output text block
        output_paragraphs = [
            "## Axiom Inference System Output",
            reasoning
        ]
        
        if artifacts:
            output_paragraphs.append("### Prescribed & Validated Artifacts")
            for idx, art in enumerate(artifacts):
                output_paragraphs.append(
                    f"**Artifact #{idx+1} ({art['type'].upper()})** - Status: `{art['status']}`\n"
                    f"```{art['type']}\n{art['content']}\n```"
                )
                if art.get("error"):
                    output_paragraphs.append(f"> [!CAUTION]\n> Validation Error: {art['error']}")
                    
        payload["experience_output"] = "\n\n".join(output_paragraphs)
        return payload
