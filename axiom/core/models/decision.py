"""
Layer 7 — Decision Record Contract.

Defines the canonical output of the Decision & Action Layer (L7).
The DecisionRecord represents the final governance status of any proposed action.
It documents policy engine checks, risk ratings, HITL routing, and audit hash chains.

Traces to:
  - Document 10 (API Specification) Section 5: Decision & Action API contract
  - Document 7 (LLD) Section 8: Decision & Action Layer contract
  - Document 9 (Database Design) Section 4.5: AuditEvent schema
  - Document 14 (Security Design) Section 6: Deterministic policy engine evaluation
  - Document 7 (LLD) Section 11: Inter-layer events (DecisionRecord)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import Field

from axiom.core.models.base import (
    OCIFBaseModel, RequestContext, DecisionOutcome, PolicyCheckResult,
    new_uuid, utc_now,
)
from axiom.core.models.cognition import CognitionResult


class PolicyCheck(OCIFBaseModel):
    """
    A single policy rule evaluation result.
    Deterministic checks per Doc 14 Section 6.
    """
    rule_name: str = Field(..., description="Unique code identifier of policy rule evaluated")
    result: PolicyCheckResult = Field(..., description="pass | fail")
    description: str = Field(..., description="Policy description")
    error_message: Optional[str] = Field(default=None, description="Detailed failure reason if result=fail")


class ExecutionLog(OCIFBaseModel):
    """Execution results for approved actions."""
    action_type: str = Field(..., description="Type of action executed")
    status: str = Field(..., description="success | failed")
    stdout: Optional[str] = Field(default=None)
    stderr: Optional[str] = Field(default=None)
    execution_time_ms: int = Field(default=0)


class DecisionRecord(OCIFBaseModel):
    """
    Canonical output of Layer 7 — Decision & Action (META CORE).

    Represents the authoritative decision made by the deterministic policy engine.
    Controls whether proposed actions are executed, queued for HITL review,
    or blocked.

    Per Doc 7 Section 8 and Doc 14 Section 6:
    - Deterministic policy engine checks
    - Composite risk calculation
    - Action authorization gate
    - Append-only cryptographically chained audit details
    """
    decision_id: str = Field(default_factory=new_uuid, description="Unique decision record ID")
    timestamp: datetime = Field(default_factory=utc_now)

    # Governance results
    outcome: DecisionOutcome = Field(default=DecisionOutcome.BLOCKED, description="Auto-approved, HITL-approved/rejected, or blocked")
    risk_score: float = Field(default=0.0, description="Calculated action risk score (0.0-1.0)")
    policy_checks: List[PolicyCheck] = Field(default_factory=list, description="List of rule evaluation outcomes")
    
    # Audit log validation variables (tamper-evident hash chain per Doc 9 Section 4.5)
    audit_event_id: str = Field(default_factory=new_uuid, description="UUID linked to the postgres audit_events table")
    prev_event_hash: Optional[str] = Field(default=None, description="SHA-256 hash of previous audit event")
    event_hash: Optional[str] = Field(default=None, description="SHA-256 hash of this audit event payload")

    # Queue tracking if human input is needed
    approval_id: Optional[str] = Field(default=None, description="Approval queue ID if HITL is required")
    comments: Optional[str] = Field(default=None, description="HITL review feedback comments")
    reviewed_by: Optional[str] = Field(default=None, description="UUID of human reviewer")
    reviewed_at: Optional[datetime] = Field(default=None)

    # Executed side-effects logs
    execution_logs: List[ExecutionLog] = Field(default_factory=list, description="Logs of executing approved action payloads")

    # Upstream layers & request contexts
    cognition_result: CognitionResult = Field(..., description="Originating model reasoning cognition results")
    request_context: RequestContext = Field(..., description="Request execution metadata envelope")
