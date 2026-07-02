import uuid
from typing import Dict, Any, List

class LearningEngine:
    """
    LearningEngine: Aggregates user feedback loops, identifies knowledge gaps,
    and structures training/evaluation datasets for controlled fine-tuning.
    """
    def __init__(self):
        self.feedback_log: List[Dict[str, Any]] = []
        self.training_candidates: List[Dict[str, Any]] = []

    def collect_feedback(self, query: str, response: str, score: int, comments: str) -> str:
        feedback_id = str(uuid.uuid4())
        entry = {
            "feedback_id": feedback_id,
            "query": query,
            "response": response,
            "score": score,
            "comments": comments,
            "status": "UNPROCESSED"
        }
        self.feedback_log.append(entry)
        
        # If feedback indicates failure (score <= 2), mark as training candidate
        if score <= 2:
            candidate = {
                "candidate_id": str(uuid.uuid4()),
                "source_feedback_id": feedback_id,
                "input_prompt": query,
                "target_corrected_output": f"[Corrected based on feedback: {comments}]",
                "approved": False
            }
            self.training_candidates.append(candidate)
            
        return feedback_id

    def list_pending_candidates(self) -> List[Dict[str, Any]]:
        return [c for c in self.training_candidates if not c["approved"]]

    def approve_candidate(self, candidate_id: str) -> bool:
        for c in self.training_candidates:
            if c["candidate_id"] == candidate_id:
                c["approved"] = True
                return True
        return False
