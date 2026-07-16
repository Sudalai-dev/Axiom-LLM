"""Dashboard routes — real, tenant-scoped usage aggregates.

Reads the ``usage_metrics`` table (written by ``api/routes/usage.py``) instead
of fabricating numbers from turn counts. All figures are scoped to the caller's
tenant; a tenant with no recorded usage yet returns zeros rather than invented
values.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from api.middleware.auth import resolve_security_context
from core.models.base import RequestContext
from storage.database import AsyncSessionLocal
from storage.models import AuditEvent, Session as DBSession, UsageMetric

router = APIRouter(prefix="/api/v1", tags=["Dashboard"])


@router.get("/dashboard/usage")
async def get_dashboard_usage(req_ctx: RequestContext = Depends(resolve_security_context)):
    """Returns aggregated, tenant-scoped usage metrics for the dashboard."""
    tenant_id = req_ctx.tenant.tenant_id
    async with AsyncSessionLocal() as db:
        totals = (await db.execute(
            select(
                func.coalesce(func.sum(UsageMetric.request_count), 0),
                func.coalesce(func.sum(UsageMetric.token_count), 0),
                func.coalesce(func.sum(UsageMetric.automation_count), 0),
                func.coalesce(func.sum(UsageMetric.cost_usd), 0.0),
            ).filter(UsageMetric.tenant_id == tenant_id)
        )).one()
        requests, tokens, automations, cost = totals

        sessions_count = (await db.execute(
            select(func.count(DBSession.session_id)).filter(DBSession.tenant_id == tenant_id)
        )).scalar() or 0
        audit_count = (await db.execute(
            select(func.count(AuditEvent.event_id)).filter(AuditEvent.tenant_id == tenant_id)
        )).scalar() or 0

    requests = int(requests or 0)
    automations = int(automations or 0)
    # Automation rate = share of requests that produced an automated solution.
    automation_rate = round(automations / requests, 3) if requests else 0.0

    return {
        "requests": requests,
        "tokens": int(tokens or 0),
        "sessions": sessions_count,
        "automation_rate": automation_rate,
        "cost_usd": round(float(cost or 0.0), 4),
        "audit_events": audit_count,
    }
