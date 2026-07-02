from typing import Dict, Any, List

class ContextEngine:
    """
    ContextEngine: Assembles the complete execution context (User, Role, 
    Project, Goals, relevant memory history, and constraints) to guide reasoning.
    """
    def __init__(self):
        pass

    def compile_context(
        self, 
        user_info: Dict[str, Any], 
        project_info: Dict[str, Any], 
        goals: List[str], 
        history: List[Dict[str, Any]], 
        heuristics: List[str]
    ) -> Dict[str, Any]:
        """
        Assembles all discrete environment variables into a single 
        unified in-memory engineering context structure.
        """
        engineering_context = {
            "current_user": user_info.get("username", "guest"),
            "role": user_info.get("role", "Viewer"),
            "project_name": project_info.get("name", "Default"),
            "project_description": project_info.get("description", ""),
            "execution_goals": goals,
            "conversation_history": history,
            "system_constraints": [
                "Local execution only",
                "Zero data leakage outside the boundary",
                "Strict validation check gating"
            ],
            "injected_heuristics": heuristics
        }
        return engineering_context
