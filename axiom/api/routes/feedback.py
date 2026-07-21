"""
Feedback routes — captures explicit user ratings on prior responses and
folds them into persistent learning memory (axiom.memory.learning_store) so
future reasoning can see what worked and what didn't.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api.middleware.auth import resolve_security_context
from api.routes.deps import learning_store
from core.models.base import RequestContext, new_uuid

router = APIRouter(prefix="/api/v1", tags=["Feedback"])


class FeedbackRequest(BaseModel):
    session_id: str
    rating: int = Field(..., ge=-1, le=1)  # -1 | 0 | 1
    note: str = Field(default="", max_length=1000)


@router.post("/feedback", status_code=201)
async def submit_feedback(
    req: FeedbackRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Records user feedback on a prior response into learning memory."""
    feedback_id = new_uuid()
    learning_store.record_feedback(
        note_id=feedback_id,
        user_id=req_ctx.user.user_id,
        project="default",
        rating=req.rating,
        note=req.note or f"Session {req.session_id} rated {req.rating:+d}",
    )
    return {"status": "success", "feedback_id": feedback_id}
