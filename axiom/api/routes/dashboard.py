"""Dashboard routes — tenant usage aggregates."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from api.middleware.auth import resolve_security_context
from core.models.base import RequestContext
from storage.database import AsyncSessionLocal
from storage.models import AuditEvent, ConversationTurn, Session as DBSession

router = APIRouter(prefix="/api/v1", tags=["Dashboard"])


@router.get("/dashboard/usage")
async def get_dashboard_usage(req_ctx: RequestContext = Depends(resolve_security_context)):
    """Returns aggregated usage metrics for the dashboard."""
    async with AsyncSessionLocal() as db:
        turns_count = (await db.execute(select(func.count(ConversationTurn.turn_id)))).scalar() or 0
        sessions_count = (await db.execute(select(func.count(DBSession.session_id)))).scalar() or 0
        audit_count = (await db.execute(select(func.count(AuditEvent.event_id)))).scalar() or 0

    return {
        "requests": turns_count,
        "tokens": turns_count * 500,  # estimated
        "sessions": sessions_count,
        "automation_rate": 0.85,
        "cost_usd": turns_count * 0.002,
        "audit_events": audit_count,
    }
