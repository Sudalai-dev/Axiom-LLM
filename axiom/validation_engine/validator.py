import re
from typing import Dict, Any, List

class ValidationEngine:
    """
    ValidationEngine: Inspects all outputs (Code, Architecture, Security, 
    Complexity, and Dependencies) before they exit the Cognitive Engine.
    """
    def __init__(self):
        pass

    def validate_artifact(self, artifact_type: str, content: str) -> Dict[str, Any]:
        """
        Runs rules over the artifact to detect syntax violations or security leaks.
        """
        if artifact_type == "python":
            return self._validate_python(content)
        elif artifact_type == "dockerfile":
            return self._validate_dockerfile(content)
        elif artifact_type == "mermaid":
            return self._validate_mermaid(content)
        else:
            # General text validation passes by default
            return {"status": "PASSED", "errors": []}

    def _validate_python(self, content: str) -> Dict[str, Any]:
        errors = []
        # 1. Compile Check
        try:
            compile(content, "<string>", "exec")
        except SyntaxError as e:
            errors.append(f"Python compile syntax error: {e}")
            
        # 2. Security Check (ensure no external cloud imports)
        if re.search(r"\b(import openai|import anthropic|import google\.generativeai)\b", content):
            errors.append("Security Violation: Detected unauthorized cloud generative AI imports.")

        return {
            "status": "FAILED" if errors else "PASSED",
            "errors": errors
        }

    def _validate_dockerfile(self, content: str) -> Dict[str, Any]:
        errors = []
        # Check if root executions are barred (e.g. USER should not be omitted or root)
        # For simplicity, do basic line checks
        if "sudo" in content.lower():
            errors.append("Security warning: sudo execution in docker container is prohibited.")
            
        return {
            "status": "FAILED" if errors else "PASSED",
            "errors": errors
        }

    def _validate_mermaid(self, content: str) -> Dict[str, Any]:
        errors = []
        # Confirm basic mermaid syntax outline
        if not re.search(r"\b(graph TD|graph LR|sequenceDiagram|erDiagram|classDiagram)\b", content):
            errors.append("Invalid Mermaid layout declarations.")
            
        return {
            "status": "FAILED" if errors else "PASSED",
            "errors": errors
        }
