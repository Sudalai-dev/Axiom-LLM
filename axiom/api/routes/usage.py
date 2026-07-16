"""Usage metering — writes real per-tenant daily aggregates to UsageMetric.

The ``usage_metrics`` table was defined but never written, so the dashboard
fabricated numbers (``turns * 500`` tokens, a fixed 0.85 automation rate, etc).
This module closes that gap: after each billable agent call the route calls
:func:`record_solution_usage`, which upserts the tenant's row for the current
UTC day with the request's real token counts and cost (from the provider when a
live model answered, or a length-based estimate for the deterministic
synthesizer path so a solution is never recorded as zero work).
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select

from core.models.base import RequestContext
from storage.database import AsyncSessionLocal
from storage.models import UsageMetric

logger = logging.getLogger("AxiomUsage")


def _estimate_tokens(output) -> int:
    """Length-based token estimate for the synthesizer path (~4 chars/token)."""
    text = getattr(output, "solution_markdown", "") or ""
    return max(1, len(text) // 4)


async def record_solution_usage(req_ctx: RequestContext, output) -> None:
    """Upserts today's usage aggregate for the tenant with this call's usage."""
    tenant_id = req_ctx.tenant.tenant_id
    tokens = int(getattr(output, "input_tokens", 0) or 0) + int(getattr(output, "output_tokens", 0) or 0)
    if tokens <= 0:
        tokens = _estimate_tokens(output)
    cost = float(getattr(output, "cost_usd", 0.0) or 0.0)
    today = datetime.now(timezone.utc).date()

    try:
        async with AsyncSessionLocal() as db:
            row = (await db.execute(
                select(UsageMetric).filter(
                    UsageMetric.tenant_id == tenant_id,
                    UsageMetric.metric_date == today,
                )
            )).scalars().first()

            if row is None:
                row = UsageMetric(
                    tenant_id=tenant_id,
                    metric_date=today,
                    token_count=tokens,
                    request_count=1,
                    automation_count=1,
                    cost_usd=cost,
                )
                db.add(row)
            else:
                row.token_count = (row.token_count or 0) + tokens
                row.request_count = (row.request_count or 0) + 1
                row.automation_count = (row.automation_count or 0) + 1
                row.cost_usd = float(row.cost_usd or 0.0) + cost
            await db.commit()
    except Exception as exc:
        # Metering is best-effort — never fail the request over a metrics write.
        logger.warning(f"Usage metering write failed: {exc}")
