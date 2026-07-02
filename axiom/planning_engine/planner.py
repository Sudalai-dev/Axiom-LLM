from typing import Dict, Any, List

class TaskStep:
    def __init__(self, step_id: str, title: str, description: str, dependencies: List[str]):
        self.step_id = step_id
        self.title = title
        self.description = description
        self.dependencies = dependencies

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "title": self.title,
            "description": self.description,
            "dependencies": self.dependencies
        }

class PlanningEngine:
    """
    PlanningEngine: Decomposes complex user goals into logical execution tasks,
    analyzes their dependencies, and constructs structured timelines.
    """
    def __init__(self):
        pass

    def generate_plan(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Simple task planner heuristics based on keywords
        steps = []
        if "api" in query.lower() or "fastapi" in query.lower():
            steps.append(TaskStep("step_1", "Define Schema", "Draft Pydantic request models", []))
            steps.append(TaskStep("step_2", "Write Endpoints", "Implement FastAPI POST and GET routes", ["step_1"]))
            steps.append(TaskStep("step_3", "Validate Code", "Verify python imports and run local syntax compiler", ["step_2"]))
        elif "deploy" in query.lower() or "docker" in query.lower():
            steps.append(TaskStep("step_1", "Draft Dockerfile", "Specify local python container base image", []))
            steps.append(TaskStep("step_2", "Write docker-compose", "Integrate app backend and vector storage services", ["step_1"]))
            steps.append(TaskStep("step_3", "Sanity Check", "Run syntax validators over yaml compose models", ["step_2"]))
        else:
            steps.append(TaskStep("step_1", "Gather Knowledge", "Scan vector store matching query terms", []))
            steps.append(TaskStep("step_2", "Analyze Architecture", "Evaluate design constraints", ["step_1"]))
            steps.append(TaskStep("step_3", "Formulate Recommendation", "Draft markdown execution specs", ["step_2"]))
            
        plan = {
            "query": query,
            "steps": [s.to_dict() for s in steps],
            "timeline_estimate": f"{len(steps) * 15} minutes",
            "risk_score": 0.05
        }
        return plan
