"""Approvals routes — human-in-the-loop (HITL) approval queue."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select

from api.middleware.auth import resolve_security_context
from core.models.base import RequestContext
from core.security import verify_rbac
from governance.hitl_queue import HITLQueue
from storage.database import AsyncSessionLocal
from storage.models import HITLApproval

router = APIRouter(prefix="/api/v1", tags=["Approvals"])


class ApprovalDecisionRequest(BaseModel):
    decision: str  # approved | rejected
    comments: str = ""


@router.get("/approvals")
async def list_approvals(req_ctx: RequestContext = Depends(resolve_security_context)):
    """Lists pending HITL approval requests for the caller's user."""
    verify_rbac(req_ctx.user.role, "approve_hitl")
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(HITLApproval).filter(HITLApproval.user_id == req_ctx.user.user_id)
        )
        return [
            {
                "approval_id": a.approval_id,
                "event_id": a.event_id,
                "status": a.status,
                "assigned_to": a.assigned_to,
                "resolved_at": str(a.resolved_at) if a.resolved_at else None,
                "comments": a.comments,
            }
            for a in result.scalars().all()
        ]


@router.post("/approvals/{approval_id}/decision")
async def resolve_approval(
    approval_id: str,
    req: ApprovalDecisionRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Resolves a pending HITL approval."""
    verify_rbac(req_ctx.user.role, "approve_hitl")
    queue = HITLQueue()
    async with AsyncSessionLocal() as db:
        approval = await queue.resolve_approval(
            db=db,
            approval_id=approval_id,
            decision=req.decision,
            user_id=req_ctx.user.user_id,
            comments=req.comments,
        )
        await db.commit()
        return {"status": approval.status, "approval_id": approval.approval_id}
