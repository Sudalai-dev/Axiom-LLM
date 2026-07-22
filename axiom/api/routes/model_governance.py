"""
Model-promotion governance routes (Phase 12) — platform-admin only.

The human-in-the-loop for promoting a fine-tuned diagram model: an admin
proposes a model change, reviews the pending queue, and explicitly approves or
rejects it. Nothing here trains or promotes a model automatically — approval is
a recorded human decision, and only an approved proposal can mint a promotable
model manifest (training.model_manifest.manifest_from_approved_proposal).
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from api.middleware.auth import resolve_security_context
from api.routes.deps import model_governance_store
from core.exceptions import ResourceNotFoundError, ValidationError
from core.models.base import RequestContext
from core.security import verify_rbac

router = APIRouter(prefix="/api/v1/admin/model-proposals", tags=["Model Governance"])


class ProposeModelChange(BaseModel):
    # `model_name` is a domain field, not a pydantic protected attribute.
    model_config = ConfigDict(protected_namespaces=())
    model_name: str = Field(..., min_length=1)
    base_model: str = Field(..., min_length=1)
    dataset_path: str = Field(..., min_length=1)
    dataset_examples: int = Field(..., ge=0)
    hyperparameters: Dict[str, Any] = Field(default_factory=dict)


class ReviewDecision(BaseModel):
    decision: str = Field(..., pattern="^(approve|reject)$")
    note: str = ""


@router.post("", status_code=201)
async def propose_model_change(
    req: ProposeModelChange,
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> Dict[str, Any]:
    """Register a promotion proposal. Always starts PENDING (never self-approved)."""
    verify_rbac(req_ctx.user.role, "manage_models")
    proposal = model_governance_store.propose(
        model_name=req.model_name,
        base_model=req.base_model,
        dataset_path=req.dataset_path,
        dataset_examples=req.dataset_examples,
        hyperparameters=req.hyperparameters,
        proposed_by=req_ctx.user.username,
    )
    return proposal.to_dict()


@router.get("")
async def list_model_proposals(
    status: Optional[str] = Query(None, description="Filter: 'pending' for the review queue"),
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> List[Dict[str, Any]]:
    """List proposals — the whole history, or just the pending review queue."""
    verify_rbac(req_ctx.user.role, "manage_models")
    items = (model_governance_store.list_pending() if status == "pending"
             else model_governance_store.list_all())
    return [p.to_dict() for p in items]


@router.post("/{proposal_id}/review")
async def review_model_proposal(
    proposal_id: str,
    req: ReviewDecision,
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> Dict[str, Any]:
    """Approve or reject a pending proposal — an explicit, recorded human decision."""
    verify_rbac(req_ctx.user.role, "manage_models")
    try:
        proposal = model_governance_store.review(
            proposal_id, decision=req.decision, reviewer=req_ctx.user.username, note=req.note,
        )
    except KeyError:
        raise ResourceNotFoundError("ModelChangeProposal", proposal_id)
    except ValueError as exc:
        raise ValidationError(str(exc))
    return proposal.to_dict()
