"""
Engineering Knowledge Platform routes.

Read/browse endpoints for the durable knowledge repository, standards, ontology,
and analytics, plus the human-in-the-loop ingestion/approval flow. Approval
endpoints reuse the existing ``approve_hitl`` RBAC action; nothing an ingestion
produces becomes active knowledge without an explicit engineer approval.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.middleware.auth import resolve_security_context
from api.routes.deps import knowledge_platform
from core.models.base import RequestContext
from core.security import verify_rbac

router = APIRouter(prefix="/api/v1/platform", tags=["Knowledge Platform"])


class IngestRequest(BaseModel):
    title: str
    content: str
    domain: str = ""
    industry: str = ""


class PendingDecisionRequest(BaseModel):
    decision: str  # approve | reject
    note: str = ""


class RuleProposal(BaseModel):
    """A proposed engineering rule ("IF any `when` signal appears, THEN `then`")."""
    name: str = Field(..., min_length=3)
    when: List[str] = Field(..., min_length=1, description="Lowercase trigger substrings")
    then: str = Field(..., min_length=3, description="The engineering decision to apply")
    rationale: str = ""
    domain: str = "Software Engineering"
    standards: List[str] = Field(default_factory=list)


@router.get("")
async def browse_platform(req_ctx: RequestContext = Depends(resolve_security_context)):
    """High-level view of what the platform knows (domains, categories, totals)."""
    coverage = knowledge_platform.analytics.coverage()
    return {
        "total_objects": coverage["total_objects"],
        "domain_coverage": coverage["domain_coverage"],
        "category_coverage": coverage["category_coverage"],
        "domain_coverage_pct": coverage["domain_coverage_pct"],
        "standards_coverage_pct": coverage["standards_coverage_pct"],
    }


@router.get("/knowledge")
async def query_knowledge(
    domain: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Ranked query over active knowledge objects (tenant + global)."""
    results = knowledge_platform.repository.query(
        domain=domain, category=category, text=q,
        tenant_id=req_ctx.tenant.tenant_id, limit=limit,
    )
    return {"count": len(results), "results": [o.to_public_dict() for o in results]}


@router.get("/standards")
async def query_standards(
    domain: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Standards with their relevant sections and compliance level."""
    return {"results": knowledge_platform.standards.query(domain=domain, q=q)}


@router.get("/ontology")
async def expand_ontology(
    term: str = Query(...),
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Semantic expansion of a term (ancestors + descendants)."""
    return {
        "term": term,
        "expanded": knowledge_platform.ontology.expand(term),
        "children": knowledge_platform.ontology.children(term),
        "ancestors": knowledge_platform.ontology.ancestors(term),
    }


@router.get("/analytics")
async def platform_analytics(req_ctx: RequestContext = Depends(resolve_security_context)):
    """Coverage, freshness, quality, and gap analysis."""
    return knowledge_platform.analytics.coverage()


@router.post("/ingest")
async def ingest_document(
    req: IngestRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Ingest a document's text into the pending queue for human review."""
    pending_id = knowledge_platform.ingestor.ingest_text(
        text=req.content,
        title=req.title,
        domain=req.domain,
        industry=req.industry,
        tenant_id=req_ctx.tenant.tenant_id,
        submitted_by=req_ctx.user.user_id,
    )
    return {"pending_id": pending_id, "status": "pending"}


@router.post("/rules/propose")
async def propose_rule(
    req: RuleProposal,
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Propose a NEW engineering rule for human review. It enters the pending
    queue and does NOT affect any solution until an admin approves it via
    ``/pending/{id}/decision`` — after which it fires on the next request
    automatically. Human-gated growth (Charter §1.3): never auto-commits."""
    pending_id = knowledge_platform.rules.propose(
        name=req.name, when=[w.lower() for w in req.when], then=req.then,
        rationale=req.rationale, domain=req.domain, standards=req.standards,
        tenant_id=req_ctx.tenant.tenant_id, submitted_by=req_ctx.user.user_id,
    )
    return {"pending_id": pending_id, "status": "pending"}


@router.get("/pending")
async def list_pending(req_ctx: RequestContext = Depends(resolve_security_context)):
    """List knowledge awaiting human approval (requires approve_hitl)."""
    verify_rbac(req_ctx.user.role, "approve_hitl")
    return {"pending": knowledge_platform.repository.list_pending(tenant_id=req_ctx.tenant.tenant_id)}


@router.post("/pending/{pending_id}/decision")
async def decide_pending(
    pending_id: str,
    req: PendingDecisionRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Approve (promote into active, versioned knowledge) or reject a pending
    entry (requires approve_hitl)."""
    verify_rbac(req_ctx.user.role, "approve_hitl")
    reviewer = req_ctx.user.user_id
    if req.decision.lower() in ("approve", "approved"):
        obj = knowledge_platform.repository.approve_pending(pending_id, reviewer=reviewer, note=req.note)
        if obj is None:
            return {"status": "not_found", "pending_id": pending_id}
        return {"status": "approved", "knowledge_id": obj.knowledge_id, "version": obj.version}
    ok = knowledge_platform.repository.reject_pending(pending_id, reviewer=reviewer, note=req.note)
    return {"status": "rejected" if ok else "not_found", "pending_id": pending_id}
