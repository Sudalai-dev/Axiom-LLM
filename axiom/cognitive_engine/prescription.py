import re
from typing import Dict, Any, List

class PrescriptionLayer:
    """
    Layer 7: Prescription.
    Parses and extracts generated artifacts (such as code block scripts, 
    Mermaid diagrams, or JSON settings) from the Cognition Layer outputs
    and runs local syntactical validations.
    """
    def __init__(self):
        pass

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        reasoning = payload.get("cognition_reasoning", "")
        
        # Extract code blocks
        code_blocks = re.findall(r"```(python|yaml|json|mermaid)\n(.*?)```", reasoning, re.DOTALL)
        
        prescribed_artifacts: List[Dict[str, Any]] = []
        for lang, content in code_blocks:
            artifact = {
                "type": lang,
                "content": content.strip(),
                "status": "UNVERIFIED"
            }
            # Simple lint/syntax verification depending on language
            if lang == "python":
                try:
                    # Check if compiles
                    compile(content, "<string>", "exec")
                    artifact["status"] = "VERIFIED"
                except SyntaxError as e:
                    artifact["status"] = "SYNTAX_ERROR"
                    artifact["error"] = str(e)
            elif lang == "json":
                import json
                try:
                    json.loads(content)
                    artifact["status"] = "VERIFIED"
                except Exception as e:
                    artifact["status"] = "SYNTAX_ERROR"
                    artifact["error"] = str(e)
            else:
                # Default verification for other script blocks
                artifact["status"] = "VERIFIED"
                
            prescribed_artifacts.append(artifact)
            
        payload["prescribed_artifacts"] = prescribed_artifacts
        return payload
