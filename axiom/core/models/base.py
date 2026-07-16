"""
OCIF Shared Enumerations & Base Types.

Defines enumerations and base types used across all OCIF layer contracts.
These represent the controlled vocabularies referenced throughout the
20-document specification set.

Traces to:
  - Document 7 (LLD) Section 11: Inter-layer contract types
  - Document 9 (Database Design) Section 4: Enum columns
  - Document 13 (Agent Design) Section 2: Agent taxonomy
  - Document 14 (Security Design) Section 3.1: RBAC roles
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------

def utc_now() -> datetime:
    """Returns the current UTC timestamp with timezone info."""
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    """Generates a new UUID4 string."""
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# RBAC Roles — Per Doc 14 Section 3.1
# ---------------------------------------------------------------------------

class UserRole(str, Enum):
    END_USER = "end_user"
    PROCESS_OWNER = "process_owner"
    COMPLIANCE_OFFICER = "compliance_officer"
    TENANT_ADMIN = "tenant_admin"
    PLATFORM_ADMIN = "platform_admin"


# ---------------------------------------------------------------------------
# Risk Levels — Per Doc 10 Section 4 / Doc 13 Section 5
# ---------------------------------------------------------------------------

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Decision Outcomes — Per Doc 10 Section 5
# ---------------------------------------------------------------------------

class DecisionOutcome(str, Enum):
    AUTO_APPROVED = "auto_approved"
    HITL_APPROVED = "hitl_approved"
    HITL_REJECTED = "hitl_rejected"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# Agent Types — Per Doc 13 Section 2
# ---------------------------------------------------------------------------

class AgentType(str, Enum):
    PLANNER = "planner"
    RETRIEVAL = "retrieval"
    TOOL_USE = "tool_use"
    VALIDATION = "validation"
    COORDINATOR = "coordinator"


# ---------------------------------------------------------------------------
# Action Types — Per Doc 12 Section 4.2
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    TOOL_CALL = "tool_call"
    CLARIFY = "clarify"
    FINAL_ANSWER = "final_answer"


# ---------------------------------------------------------------------------
# Ingestion Status — Per Doc 10 Section 3
# ---------------------------------------------------------------------------

class IngestionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Workflow Execution Status — Per Doc 10 Section 4
# ---------------------------------------------------------------------------

class ExecutionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Source Types — Per Doc 11 Section 5
# ---------------------------------------------------------------------------

class SourceType(str, Enum):
    UPLOAD = "upload"
    API = "api"
    DATABASE = "database"
    WEB = "web"


# ---------------------------------------------------------------------------
# LLM Providers — Per Doc 10 Section 6
# ---------------------------------------------------------------------------

class LLMProvider(str, Enum):
    OPENAI = "openai"
    CLAUDE = "claude"
    GEMINI = "gemini"
    LLAMA = "llama"
    OPENCODE = "opencode"  # local free-tier agent runtime (freemium plan)
    AUTO = "auto"


# ---------------------------------------------------------------------------
# Approval Status — Per Doc 10 Section 2.4
# ---------------------------------------------------------------------------

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


# ---------------------------------------------------------------------------
# Coordination Pattern — Per Doc 13 Section 6
# ---------------------------------------------------------------------------

class CoordinationPattern(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"
    DEBATE = "debate"


# ---------------------------------------------------------------------------
# Policy Rule Result — Per Doc 10 Section 5
# ---------------------------------------------------------------------------

class PolicyCheckResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"


# ---------------------------------------------------------------------------
# OCIF Base Model
# ---------------------------------------------------------------------------

class OCIFBaseModel(BaseModel):
    """
    Base model for all OCIF Pydantic DTOs.

    Provides common configuration and serialization behavior.
    All OCIF models use this as their parent.
    """

    class Config:
        # Allow population by field name
        populate_by_name = True
        # Use enum values in serialization
        use_enum_values = True
        # Validate on assignment
        validate_assignment = True
        # Serialize datetime as ISO 8601
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


# ---------------------------------------------------------------------------
# Tenant Context — Attached to every request
# ---------------------------------------------------------------------------

class TenantContext(OCIFBaseModel):
    """
    Resolved tenant context attached to every request after gateway processing.

    Populated by the tenant_resolver middleware (Layer 2) from JWT claims.
    Propagated through all downstream layers for RLS enforcement and
    Pinecone namespace isolation.
    """
    tenant_id: str = Field(..., description="UUID of the resolved tenant")
    tenant_name: str = Field(..., description="Human-readable tenant name")
    industry: str = Field(default="general", description="Industry vertical for prompt customization")
    isolation_mode: str = Field(default="shared", description="shared | dedicated")
    rate_limit_tier: str = Field(default="standard", description="standard | enterprise")


# ---------------------------------------------------------------------------
# User Context — Attached to every request
# ---------------------------------------------------------------------------

class UserContext(OCIFBaseModel):
    """
    Resolved user context from the authenticated JWT token.
    Used for RBAC enforcement at both API and row level.
    """
    user_id: str = Field(..., description="UUID of the authenticated user")
    username: str = Field(..., description="User's login name")
    role: UserRole = Field(..., description="User's RBAC role per Doc 14 Section 3.1")
    tenant_id: str = Field(..., description="Tenant the user belongs to")
    department: Optional[str] = Field(default=None, description="User's department for scoped access")
    permissions: Dict[str, bool] = Field(default_factory=dict, description="Resolved permission flags")


# ---------------------------------------------------------------------------
# Request Context — The envelope carried through all 8 layers
# ---------------------------------------------------------------------------

class RequestContext(OCIFBaseModel):
    """
    Master request context envelope that flows through all 8 OCIF layers.

    Created at Layer 2 (Gateway), enriched at each layer, and used for
    correlation, tenant isolation, and audit tracing.
    """
    correlation_id: str = Field(default_factory=new_uuid, description="Unique request trace ID per Doc 10")
    session_id: Optional[str] = Field(default=None, description="Conversation session ID")
    tenant: TenantContext = Field(..., description="Resolved tenant context")
    user: UserContext = Field(..., description="Resolved user context")
    timestamp: datetime = Field(default_factory=utc_now, description="Request ingestion timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Layer-specific metadata accumulator")
