"""
OCIF Public Router — Layer 8.

Implements all public facing REST endpoints per Document 10 specifications.
Runs request context resolution, invokes all 8 cognitive layers sequentially,
and returns structured RFC 7807 responses.

Traces to:
  - Document 10 (API Specification) Section 2: Public API - Layer 8
  - Document 10 (API Specification) Section 5: Decision & Action API
  - Document 7 (LLD) Section 9: Experience Layer contract
"""

import json
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import date
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Header, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, text
from axiom.core.config import settings
from axiom.core.security import create_access_token


from axiom.storage.database import get_db
from axiom.core.models.base import RequestContext, UserRole, DecisionOutcome
from axiom.core.exceptions import ValidationError, PolicyViolationError, HITLRequiredError
from axiom.gateway.auth_middleware import resolve_security_context, get_request_context
from axiom.gateway.tenant_resolver import bind_tenant_to_database_session, verify_tenant_isolation
from axiom.gateway.rate_limiter import rate_limiter

# Core layer service instantiations
from axiom.layer1_perception.service import PerceptionService
from axiom.layer3_context.service import ContextService
from axiom.layer4_knowledge.service import KnowledgeService
from axiom.layer5_orchestration.service import OrchestrationService
from axiom.layer6_cognition.service import CognitionService
from axiom.layer7_decision.service import DecisionService
from axiom.storage.models import Tenant, Policy, HITLApproval, AuditEvent

logger = logging.getLogger("AxiomPublicRouter")
router = APIRouter(prefix="/api/v1")

# Services Singletons
l1_perception = PerceptionService()
l3_context = ContextService()
l4_knowledge = KnowledgeService()
l5_orchestration = OrchestrationService()
l6_cognition = CognitionService()
l7_decision = DecisionService()


# ---------------------------------------------------------------------------
# Pydantic Schemas for Requests/Responses
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str
    password: str


class ChatLegacyRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class ChatAttachment(BaseModel):
    type: str = Field(..., description="document | image")
    uri: str = Field(..., description="File path or URL")


class ChatMessagesRequest(BaseModel):
    session_id: Optional[str] = Field(default=None)
    message: str = Field(..., min_length=1)
    attachments: List[ChatAttachment] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    turn_id: str
    rating: int = Field(..., ge=-1, le=1)  # -1 | 0 | 1
    correction_text: Optional[str] = Field(default=None)


class ApprovalDecisionRequest(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    comments: Optional[str] = Field(default=None)


class PolicyCreateRequest(BaseModel):
    name: str = Field(..., min_length=3)
    rule_definition: Dict[str, Any] = Field(..., description="JSON rules DSL")
    risk_threshold: float = Field(default=0.700, ge=0.0, le=1.0)


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2)
    industry: str = Field(..., min_length=2)
    isolation_mode: str = Field(default="shared")


# ---------------------------------------------------------------------------
# 2.1 Chat Endpoint
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Auth Login & Legacy Chat Compatibility Endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/login", tags=["Auth"])
async def auth_login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Simulates identity verification. Validates user credentials 
    and generates signed JWT tokens with claims (Doc 14 Section 3).
    """
    if req.username == "admin" and req.password == "admin123":
        payload = {
            "sub": "admin_user",
            "user_id": "11111111-1111-1111-1111-222222222222",
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "tenant_name": "Axiom Enterprise Inc",
            "role": "platform_admin",
            "industry": "IoT Systems & Robotics",
            "isolation_mode": "shared",
            "rate_limit_tier": "unlimited"
        }
        token = create_access_token(payload)
        return {"access_token": token, "token_type": "bearer"}
        
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Incorrect username or password validation mismatch."
    )


@router.post("/chat", response_model=Dict[str, Any], tags=["Chat"])
async def post_chat_legacy(
    req: ChatLegacyRequest,
    db: AsyncSession = Depends(get_db),
    req_ctx: RequestContext = Depends(resolve_security_context)
):
    """Legacy chat compatibility route mapping directly to OCIF post_chat_message."""
    msg_req = ChatMessagesRequest(
        session_id=req.session_id,
        message=req.query,
        attachments=[]
    )
    return await post_chat_message(msg_req, db, req_ctx)


@router.post("/chat/messages", response_model=Dict[str, Any], tags=["Chat"])
async def post_chat_message(
    req: ChatMessagesRequest,
    db: AsyncSession = Depends(get_db),
    req_ctx: RequestContext = Depends(resolve_security_context)
):
    """
    Core Chat Endpoint. Routes query sequentially through L1-L8 pipeline.
    """
    tenant_id = req_ctx.tenant.tenant_id
    user_id = req_ctx.user.user_id

    # 1. Enforce rate limiting checks
    rate_limiter.check_rate_limit(tenant_id, req_ctx.tenant.rate_limit_tier)

    # 2. Set database connection session RLS parameter
    await bind_tenant_to_database_session(db, tenant_id)

    # Bind request metadata query text
    req_ctx.metadata["query"] = req.message
    session_id = req.session_id or str(uuid.uuid4())
    req_ctx.session_id = session_id

    # 3. Layer 1 — Perception Run
    attachments_payload = [{"type": a.type, "uri": a.uri} for a in req.attachments]
    perception_event = await l1_perception.process_input(
        query=req.message,
        attachments=attachments_payload,
        client_metadata={"user_agent": "FastAPI Client"}
    )
    
    if not perception_event.is_safe:
        raise ValidationError(
            detail=f"Query blocked by perception screening: {perception_event.rejection_reason}"
        )

    try:
        # 4. Layer 3 — Context Intelligence Run
        context_frame = await l3_context.compile_context(
            db=db,
            request_context=req_ctx,
            query=perception_event.raw_text
        )

        # Record User turn to history
        await l3_context.record_user_turn(
            db=db,
            session_id=session_id,
            tenant_id=tenant_id,
            role="user",
            content=perception_event.raw_text
        )

        # 5. Layer 4 — Knowledge Enrichment Run
        enriched_context = await l4_knowledge.enrich_context(
            db=db,
            context_frame=context_frame
        )

        # 6. Layer 5 — Orchestration Agent Run
        orchestration_plan, system_prompt = await l5_orchestration.execute_orchestration(
            db=db,
            enriched_context=enriched_context,
            query=perception_event.raw_text
        )

        # 7. Layer 6 — Cognition Model Run
        cognition_result = await l6_cognition.execute_reasoning(
            request_context=req_ctx,
            orchestration_plan=orchestration_plan,
            prompt=system_prompt,
            selected_provider=settings.llm.default_provider
        )

        # 8. Layer 7 — Decision & Action (META CORE) Run
        decision_record = await l7_decision.evaluate_and_execute(
            db=db,
            cognition_result=cognition_result
        )

        # Record assistant reply to turns history
        await l3_context.record_user_turn(
            db=db,
            session_id=session_id,
            tenant_id=tenant_id,
            role="assistant",
            content=decision_record.cognition_result.content
        )

        # Return public response matching Doc 10 Section 2.1
        citations_payload = [
            {
                "doc_id": c.doc_id,
                "title": c.title,
                "excerpt_ref": c.text[:120] + "..."
            }
            for c in decision_record.cognition_result.orchestration_plan.enriched_context.retrieved_chunks
        ]

        return {
            "session_id": session_id,
            "response": decision_record.cognition_result.content,
            "citations": citations_payload,
            "confidence": decision_record.cognition_result.confidence,
            "decision_trace_id": decision_record.audit_event_id
        }

    except (PolicyViolationError, HITLRequiredError) as exc:
        # Commit context modifications and propagate to standard API error handler
        await db.commit()
        raise
    except Exception as e:
        logger.error(f"Execution pipeline error: {e}", exc_info=True)
        await db.rollback()
        raise


# ---------------------------------------------------------------------------
# 2.2 Feedback Endpoint
# ---------------------------------------------------------------------------

@router.post("/feedback", status_code=status.HTTP_201_CREATED, tags=["Feedback"])
async def post_feedback(
    req: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    req_ctx: RequestContext = Depends(resolve_security_context)
):
    """
    Submits user ratings feedback (Doc 10 Section 2.2).
    """
    await bind_tenant_to_database_session(db, req_ctx.tenant.tenant_id)

    fid = str(uuid.uuid4())
    sql = text(
        "INSERT INTO feedback (feedback_id, tenant_id, turn_id, rating, correction_text) "
        "VALUES (:fid, :tid, :turn_id, :rating, :corr)"
    )
    await db.execute(
        sql,
        {
            "fid": fid,
            "tid": req_ctx.tenant.tenant_id,
            "turn_id": req.turn_id,
            "rating": req.rating,
            "corr": req.correction_text
        }
    )
    return {"status": "success", "feedback_id": fid}


# ---------------------------------------------------------------------------
# 2.3 Dashboards Endpoint
# ---------------------------------------------------------------------------

@router.get("/dashboard/usage", tags=["Dashboard"])
async def get_dashboard_usage(
    db: AsyncSession = Depends(get_db),
    req_ctx: RequestContext = Depends(resolve_security_context)
):
    """
    Returns usage stats aggregates for the active tenant.
    """
    tenant_id = req_ctx.tenant.tenant_id
    await bind_tenant_to_database_session(db, tenant_id)

    # Aggregate token/request count logs
    sql = (
        "SELECT COALESCE(SUM(request_count), 0), COALESCE(SUM(token_count), 0), "
        "COALESCE(SUM(cost_usd), 0), COALESCE(SUM(automation_count), 0) "
        "FROM usage_metrics WHERE tenant_id = :tenant_id"
    )
    res = await db.execute(text(sql), {"tenant_id": tenant_id})
    row = res.fetchone()

    return {
        "requests": int(row[0]) if row else 0,
        "tokens": int(row[1]) if row else 0,
        "cost_usd": float(row[2]) if row else 0.0,
        "automation_rate": float(row[3] / max(1, row[0])) if row else 0.0
    }


# ---------------------------------------------------------------------------
# 2.4 HITL Approvals Queue
# ---------------------------------------------------------------------------

@router.get("/approvals", tags=["Approvals"])
async def list_pending_approvals(
    db: AsyncSession = Depends(get_db),
    req_ctx: RequestContext = Depends(resolve_security_context)
):
    """
    Lists pending manual approvals. Restricted to Process Owner and above roles.
    """
    tenant_id = req_ctx.tenant.tenant_id
    user_role = req_ctx.user.role

    # Enforce RBAC per Matrix
    from axiom.core.security import verify_rbac
    verify_rbac(user_role, "approve_hitl")

    await bind_tenant_to_database_session(db, tenant_id)

    sql = (
        "SELECT a.approval_id, a.event_id, e.actor, e.risk_score, e.created_at "
        "FROM hitl_approvals a "
        "JOIN audit_events e ON a.event_id = e.event_id "
        "WHERE a.tenant_id = :tenant_id AND a.status = 'pending'"
    )
    res = await db.execute(text(sql), {"tenant_id": tenant_id})
    rows = res.fetchall()

    return [
        {
            "approval_id": r[0],
            "event_id": r[1],
            "summary": f"Action proposed by agent: actor: {r[2]}",
            "risk_score": float(r[3]),
            "requested_at": r[4].isoformat() if r[4] else None
        }
        for r in rows
    ]


@router.post("/approvals/{approval_id}/decision", tags=["Approvals"])
async def post_approval_decision(
    approval_id: str,
    req: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    req_ctx: RequestContext = Depends(resolve_security_context)
):
    """
    Submits reviewer decision to resolve a pending approval.
    """
    tenant_id = req_ctx.tenant.tenant_id
    user_role = req_ctx.user.role

    from axiom.core.security import verify_rbac
    verify_rbac(user_role, "approve_hitl")

    await bind_tenant_to_database_session(db, tenant_id)

    from axiom.layer7_decision.hitl_queue import HITLQueue
    queue = HITLQueue()
    
    # Resolve ticket status and cascade outcome updates to parent AuditEvent
    approval = await queue.resolve_approval(
        db=db,
        approval_id=approval_id,
        tenant_id=tenant_id,
        decision=req.decision,
        user_id=req_ctx.user.user_id,
        comments=req.comments
    )
    
    return {"status": "success", "resolved_status": approval.status}


# ---------------------------------------------------------------------------
# 7. Admin / Configuration Routes
# ---------------------------------------------------------------------------

@router.post("/admin/policies", status_code=status.HTTP_201_CREATED, tags=["Admin"])
async def create_policy(
    req: PolicyCreateRequest,
    db: AsyncSession = Depends(get_db),
    req_ctx: RequestContext = Depends(resolve_security_context)
):
    """
    Creates a new policy rules-as-code DSL configuration.
    """
    tenant_id = req_ctx.tenant.tenant_id
    from axiom.core.security import verify_rbac
    verify_rbac(req_ctx.user.role, "configure_policies")

    await bind_tenant_to_database_session(db, tenant_id)

    db_policy = Policy(
        tenant_id=tenant_id,
        name=req.name,
        rule_definition=json.dumps(req.rule_definition),
        risk_threshold=req.risk_threshold
    )
    db.add(db_policy)
    await db.flush()

    return {"policy_id": db_policy.policy_id, "status": "active"}


@router.post("/admin/tenants", status_code=status.HTTP_201_CREATED, tags=["Admin"])
async def onboard_tenant(
    req: TenantCreateRequest,
    db: AsyncSession = Depends(get_db),
    req_ctx: RequestContext = Depends(resolve_security_context)
):
    """
    Onboards a new enterprise tenant. Restricted to Platform Admin.
    """
    from axiom.core.security import verify_rbac
    verify_rbac(req_ctx.user.role, "manage_tenants")

    # Check duplicate
    existing = await db.execute(select(Tenant).filter(Tenant.name == req.name))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Tenant name already exists")

    tenant = Tenant(
        name=req.name,
        industry=req.industry,
        isolation_mode=req.isolation_mode
    )
    db.add(tenant)
    await db.flush()

    return {"tenant_id": tenant.tenant_id, "status": "onboarded"}


