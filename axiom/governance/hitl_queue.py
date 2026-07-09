"""
OCIF Human-in-the-Loop (HITL) Queue Service — Layer 7 (META CORE).

Tracks manual authorization request lifecycles. Registers pending items
inside hitl_approvals database schema (per Doc 9 Section 4.5).

Traces to:
  - Document 10 (API Specification) Section 2.4: Approvals (HITL) API
  - Document 9 (Database Design) Section 4.5: hitl_approvals schema
"""

import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import ResourceNotFoundError
from core.models.base import ApprovalStatus
from storage.models import HITLApproval, AuditEvent

logger = logging.getLogger("AxiomHITLQueue")


class HITLQueue:
    """
    Manages pending manual action approvals.
    """

    async def create_approval_request(
        self,
        db: AsyncSession,
        event_id: str,
        tenant_id: str
    ) -> str:
        """
        Registers a pending manual verification ticket linked to an audit event.
        """
        logger.info(f"Registering HITL approval ticket for audit event: '{event_id}'")

        approval = HITLApproval(
            event_id=event_id,
            tenant_id=tenant_id,
            status=ApprovalStatus.PENDING.value
        )
        db.add(approval)
        await db.flush()  # Populates auto-generated ID

        logger.info(f"Successfully queued approval ticket: '{approval.approval_id}'")
        return approval.approval_id

    async def resolve_approval(
        self,
        db: AsyncSession,
        approval_id: str,
        tenant_id: str,
        decision: str,  # approved | rejected
        user_id: str,
        comments: Optional[str] = None
    ) -> HITLApproval:
        """
        Resolves a pending approval ticket. Updates status and marks timestamps.
        """
        logger.info(f"Resolving HITL approval ticket: '{approval_id}' as '{decision}' by User: '{user_id}'")

        # 1. Fetch approval request
        result = await db.execute(
            select(HITLApproval)
            .filter(HITLApproval.approval_id == approval_id)
            .filter(HITLApproval.tenant_id == tenant_id)
        )
        approval = result.scalars().first()
        if not approval:
            raise ResourceNotFoundError("HITLApproval", approval_id)

        if approval.status != ApprovalStatus.PENDING.value:
            raise ValueError(f"Approval ticket {approval_id} has already been resolved.")

        # 2. Update status properties
        status_val = ApprovalStatus.APPROVED.value if decision.lower() == "approved" else ApprovalStatus.REJECTED.value
        approval.status = status_val
        approval.assigned_to = user_id
        approval.resolved_at = datetime.now(timezone.utc)
        approval.comments = comments

        # 3. Update parent AuditEvent outcome
        # (Must sync the execution decision from the manual reviewer)
        audit_outcome = "hitl_approved" if decision.lower() == "approved" else "hitl_rejected"
        await db.execute(
            update(AuditEvent)
            .where(AuditEvent.event_id == approval.event_id)
            .values(decision=audit_outcome)
        )

        return approval
