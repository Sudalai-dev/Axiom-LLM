from typing import Dict, Any, List

class ModelProfile:
    def __init__(self, name: str, size: str, path: str, performance_score: float):
        self.name = name
        self.size = size
        self.path = path
        self.performance_score = performance_score

class ModelRegistryEngine:
    """
    ModelRegistryEngine: Coordinates model selection, versioning, health tracking,
    and routing configs for pluggable local runtimes.
    """
    def __init__(self):
        self.registry: Dict[str, ModelProfile] = {
            "qwen2.5-coder": ModelProfile("qwen2.5-coder", "7B", "local/qwen/", 0.94),
            "llama3.1-8b": ModelProfile("llama3.1-8b", "8B", "local/llama/", 0.92),
            "mistral-nemo": ModelProfile("mistral-nemo", "12B", "local/mistral/", 0.89)
        }
        self.active_model = "qwen2.5-coder"

    def get_active_profile(self) -> Dict[str, Any]:
        profile = self.registry.get(self.active_model)
        return {
            "model_name": profile.name,
            "parameters": profile.size,
            "local_path": profile.path,
            "reliability_rating": profile.performance_score
        }

    def route_inference(self, task_type: str) -> str:
        """Selects the best local model according to task demands."""
        if task_type == "Code Generation":
            return "qwen2.5-coder"
        else:
            return "llama3.1-8b"
            
    def set_active_model(self, model_name: str):
        if model_name in self.registry:
            self.active_model = model_name
            return True
        return False
