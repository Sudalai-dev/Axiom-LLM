"""
OCIF Audit Logger Service — Layer 7 (META CORE).

Enforces SHA-256 cryptographic chain link persistence in audit_events table.
Ensures fail-closed circuit breaking if audit writes fail (per Doc 18 Section 7).

Traces to:
  - Document 9 (Database Design) Section 4.5: audit_events schema
  - Document 18 (Deployment Guide) Section 7: Audit log write failures (fail-closed)
  - Document 14 (Security Design) Section 2: Defense-in-depth audits
"""

import json
import logging
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from axiom.core.exceptions import AuditWriteError
from axiom.core.security import calculate_event_hash
from axiom.storage.models import AuditEvent

logger = logging.getLogger("AxiomAuditLogger")


class AuditLogger:
    """
    Manages tamper-evident audit logging.
    """

    async def log_event(
        self,
        db: AsyncSession,
        tenant_id: str,
        session_id: Optional[str],
        actor: str,
        input_snapshot: Dict[str, Any],
        retrieved_sources: List[Dict[str, Any]],
        model_used: str,
        policy_checks: List[Dict[str, Any]],
        risk_score: float,
        decision: str,
        action_taken: Optional[Dict[str, Any]] = None
    ) -> AuditEvent:
        """
        Creates and commits an immutable hash-chained AuditEvent record.
        
        Raises AuditWriteError if anything fails (fail-closed invariant).
        """
        logger.info(f"Writing tamper-evident audit log event for tenant {tenant_id}")

        try:
            # 1. Fetch previous event hash for tenant
            result = await db.execute(
                select(AuditEvent)
                .filter(AuditEvent.tenant_id == tenant_id)
                .order_by(AuditEvent.created_at.desc())
                .limit(1)
            )
            prev_event = result.scalars().first()
            prev_hash = prev_event.event_hash if prev_event else None

            # 2. Construct deterministic event payload for hashing
            event_payload = {
                "tenant_id": tenant_id,
                "session_id": session_id,
                "actor": actor,
                "input_snapshot": input_snapshot,
                "retrieved_sources": retrieved_sources,
                "model_used": model_used,
                "policy_checks": policy_checks,
                "risk_score": float(risk_score),
                "decision": decision,
                "action_taken": action_taken
            }

            # 3. Calculate SHA-256 hash chain link
            event_hash = calculate_event_hash(prev_hash, event_payload)

            # 4. Write to DB table
            db_event = AuditEvent(
                tenant_id=tenant_id,
                session_id=session_id,
                actor=actor,
                input_snapshot=json.dumps(input_snapshot),
                retrieved_sources=json.dumps(retrieved_sources),
                model_used=model_used,
                policy_checks=json.dumps(policy_checks),
                risk_score=risk_score,
                decision=decision,
                action_taken=json.dumps(action_taken) if action_taken else None,
                prev_event_hash=prev_hash,
                event_hash=event_hash
            )
            
            db.add(db_event)
            await db.flush()  # Lock and populate properties within session scope
            
            logger.info(f"Audit log committed. Event ID: '{db_event.event_id}'. Chain Link: '{event_hash[:8]}...'")
            return db_event

        except Exception as e:
            logger.critical(f"Fail-closed: Audit logger write operation failed: {e}")
            # Raise the critical system error to abort transaction operations
            raise AuditWriteError(
                detail=f"Fail-closed: Audit logging failed. Action execution is blocked. Error: {str(e)}"
            )
