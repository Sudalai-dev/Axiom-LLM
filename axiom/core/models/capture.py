"""
Layer 2 — Capture Event Contract.

Defines the canonical output of the Capture/Gateway Layer (L2).
The CaptureEvent augments the PerceptionEvent with authentication,
tenant resolution, session binding, and rate-limit metadata.

Traces to:
  - Document 6 (LLD) Section 2: API Gateway & Auth Service
  - Document 7 (LLD) Section 3: Capture Layer contract
  - Document 7 (LLD) Section 11: Inter-layer events (CaptureEvent)
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import Field

from axiom.core.models.base import (
    OCIFBaseModel, TenantContext, UserContext, new_uuid, utc_now,
)
from axiom.core.models.perception import PerceptionEvent


class SessionInfo(OCIFBaseModel):
    """Active session metadata, resolved or created by the session service."""
    session_id: str = Field(default_factory=new_uuid)
    is_new_session: bool = Field(default=False)
    turn_number: int = Field(default=1, description="Sequential turn index within the session")
    created_at: datetime = Field(default_factory=utc_now)


class CaptureEvent(OCIFBaseModel):
    """
    Canonical output of Layer 2 — Capture / Gateway.

    Wraps the PerceptionEvent with fully resolved authentication,
    tenant context, session binding, and request envelope metadata.
    This is the first tenant-scoped event in the pipeline.

    Per Doc 6 Section 2 and Doc 7 Section 3:
    - JWT validation and user resolution
    - Tenant ID resolution from token claims
    - Session creation or retrieval (Redis-backed)
    - Rate limit check (pass/reject)
    - Correlation ID injection
    """
    event_id: str = Field(default_factory=new_uuid, description="Unique capture event ID")
    correlation_id: str = Field(default_factory=new_uuid, description="End-to-end request trace ID")
    timestamp: datetime = Field(default_factory=utc_now)

    # Upstream event
    perception_event: PerceptionEvent = Field(..., description="The originating perception event")

    # Authentication & tenant resolution
    tenant: TenantContext = Field(..., description="Resolved tenant context from JWT")
    user: UserContext = Field(..., description="Authenticated user context from JWT")

    # Session
    session: SessionInfo = Field(..., description="Active conversation session")

    # Rate limit result
    rate_limit_remaining: int = Field(default=-1, description="Remaining requests in current window; -1 = not checked")
    rate_limit_tier: str = Field(default="standard", description="standard | enterprise")

    # Gateway metadata
    gateway_metadata: Dict[str, Any] = Field(default_factory=dict, description="Gateway-injected metadata (IP, user-agent, etc.)")
