"""
OCIF Database Models.

Conforms strictly to the PostgreSQL-compatible schema defined in Document 9, 
Sections 4.1–4.6, supporting both local SQLite execution and production PostgreSQL.

Traces to:
  - Document 9 (Database Design) Section 4: Core PostgreSQL Schema
  - Document 7 (LLD) Section 12 Invariant 4: Fail-closed governance
  - Document 14 (Security Design) Section 3: Row-Level Security
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, Text, ForeignKey, 
    Numeric, Date, Index, event
)
from sqlalchemy.orm import relationship
from storage.database import Base


def new_uuid_str() -> str:
    """Generates a random UUID4 string."""
    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Returns the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ===========================================================================
# 4.1 Identity & Tenancy
# ===========================================================================

class Tenant(Base):
    """
    Tenants table per Doc 9 Section 4.1.
    """
    __tablename__ = "tenants"

    tenant_id = Column(String(36), primary_key=True, default=new_uuid_str)
    name = Column(String(255), nullable=False)
    industry = Column(String(100), nullable=True)
    isolation_mode = Column(String(20), default="shared")  # shared | dedicated
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")
    sessions = relationship("Session", back_populates="tenant", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="tenant", cascade="all, delete-orphan")
    tools = relationship("Tool", back_populates="tenant", cascade="all, delete-orphan")
    workflows = relationship("AgentWorkflow", back_populates="tenant", cascade="all, delete-orphan")
    policies = relationship("Policy", back_populates="tenant", cascade="all, delete-orphan")


class User(Base):
    """
    Users table per Doc 9 Section 4.1.
    Note: external_idp_subject maps to the subject claim in JWT SSO tokens.
    """
    __tablename__ = "users"

    user_id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(String(36), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    external_idp_subject = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False)  # RBAC role per UserRole enum
    department = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Unique constraint per tenant for IdP mapping
    __table_args__ = (
        Index("uq_tenant_user_subject", "tenant_id", "external_idp_subject", unique=True),
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="users")
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    long_term_memories = relationship("LongTermMemory", back_populates="user", cascade="all, delete-orphan")
    workflows = relationship("AgentWorkflow", back_populates="user")
    hitl_approvals = relationship("HITLApproval", back_populates="assigned_user")


# ===========================================================================
# 4.2 Conversation & Context (Layer 3)
# ===========================================================================

class Session(Base):
    """
    Sessions table per Doc 9 Section 4.2.
    Defines a unique conversational context session.
    """
    __tablename__ = "sessions"

    session_id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(String(36), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    channel = Column(String(50), default="chat")
    started_at = Column(DateTime, default=utc_now)
    ended_at = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="sessions")
    user = relationship("User", back_populates="sessions")
    turns = relationship("ConversationTurn", back_populates="session", cascade="all, delete-orphan")
    long_term_memories = relationship("LongTermMemory", back_populates="session")


class ConversationTurn(Base):
    """
    Conversation turns table per Doc 9 Section 4.2.
    Tracks messages within a session alongside intent, entities, and context data.
    """
    __tablename__ = "conversation_turns"

    turn_id = Column(String(36), primary_key=True, default=new_uuid_str)
    session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(36), nullable=False)
    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    intent = Column(String(100), nullable=True)
    entities = Column(Text, nullable=True)  # JSON-encoded string
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    session = relationship("Session", back_populates="turns")
    feedback_entries = relationship("Feedback", back_populates="turn", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_turns_session_time", "session_id", "created_at"),
    )


class LongTermMemory(Base):
    """
    Long Term Memory table per Doc 9 Section 4.2.
    Stores synthesized user profile facts across conversation sessions.
    """
    __tablename__ = "long_term_memory"

    fact_id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(String(36), nullable=False)
    user_id = Column(String(36), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    fact = Column(Text, nullable=False)
    source_session_id = Column(String(36), ForeignKey("sessions.session_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    user = relationship("User", back_populates="long_term_memories")
    session = relationship("Session", back_populates="long_term_memories")


# ===========================================================================
# 4.3 Knowledge Metadata (Layer 4)
# ===========================================================================

class Document(Base):
    """
    Documents ingestion metadata table per Doc 9 Section 4.3.
    Tracks document file properties and current indexing state.
    """
    __tablename__ = "documents"

    doc_id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(String(36), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    source_type = Column(String(50), nullable=False)  # upload | api | database | web
    storage_uri = Column(String(1000), nullable=True)  # S3 or local path
    ingestion_status = Column(String(30), default="pending")  # IngestionStatus
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    tenant = relationship("Tenant", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """
    Document chunks table per Doc 9 Section 4.3.
    Holds text pieces and refers to Pinecone vectors.
    """
    __tablename__ = "document_chunks"

    chunk_id = Column(String(36), primary_key=True, default=new_uuid_str)
    doc_id = Column(String(36), ForeignKey("documents.doc_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(36), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    pinecone_vector_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    document = relationship("Document", back_populates="chunks")

    __table_args__ = (
        Index("idx_chunks_doc_id", "doc_id"),
    )


# ===========================================================================
# 4.4 Orchestration & Tools (Layer 5)
# ===========================================================================

class Tool(Base):
    """
    Tools registration table per Doc 9 Section 4.4.
    """
    __tablename__ = "tools"

    tool_id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(String(36), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=True)  # NULL = global tool
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    input_schema = Column(Text, nullable=False)  # JSON-encoded string
    output_schema = Column(Text, nullable=False)  # JSON-encoded string
    risk_level = Column(String(20), default="low")  # low | medium | high
    requires_approval = Column(Boolean, default=False)
    endpoint = Column(String(1000), nullable=False)
    is_active = Column(Boolean, default=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="tools")


class AgentWorkflow(Base):
    """
    Agent workflows definition table per Doc 9 Section 4.4.
    """
    __tablename__ = "agent_workflows"

    workflow_id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(String(36), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    definition = Column(Text, nullable=False)  # JSON-encoded string mapping LangGraph definitions
    created_by = Column(String(36), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    tenant = relationship("Tenant", back_populates="workflows")
    user = relationship("User", back_populates="workflows")


# ===========================================================================
# 4.5 Decision & Action / Audit (Layer 7 — Immutable)
# ===========================================================================

class Policy(Base):
    """
    Policies rules table per Doc 9 Section 4.5.
    """
    __tablename__ = "policies"

    policy_id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(String(36), ForeignKey("tenants.tenant_id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    rule_definition = Column(Text, nullable=False)  # JSON-encoded DSL representation
    risk_threshold = Column(Numeric(4, 3), default=0.700)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    tenant = relationship("Tenant", back_populates="policies")


class AuditEvent(Base):
    """
    Audit log events table per Doc 9 Section 4.5.
    Strictly append-only (no update/delete permissions). Holds full request logs,
    policy validations, risk evaluations, and SHA-256 chain links for tamper-evidence.
    """
    __tablename__ = "audit_events"

    event_id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(String(36), nullable=False)
    session_id = Column(String(36), nullable=True)
    actor = Column(String(20), nullable=False)  # agent | human | system
    input_snapshot = Column(Text, nullable=True)  # JSON snapshot of inputs
    retrieved_sources = Column(Text, nullable=True)  # JSON snapshot of citations
    model_used = Column(String(100), nullable=True)
    policy_checks = Column(Text, nullable=True)  # JSON snapshot of rule checks
    risk_score = Column(Numeric(4, 3), nullable=True)
    decision = Column(String(30), nullable=False)  # DecisionOutcome
    action_taken = Column(Text, nullable=True)  # JSON details of action
    prev_event_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=False)  # SHA-256 hash of this event
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    hitl_approvals = relationship("HITLApproval", back_populates="audit_event", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_audit_tenant_time", "tenant_id", "created_at"),
    )


class HITLApproval(Base):
    """
    Human-in-the-loop approvals table per Doc 9 Section 4.5.
    Manages manual approval queues for actions exceeding risk scores.
    """
    __tablename__ = "hitl_approvals"

    approval_id = Column(String(36), primary_key=True, default=new_uuid_str)
    event_id = Column(String(36), ForeignKey("audit_events.event_id", ondelete="CASCADE"), nullable=False)
    tenant_id = Column(String(36), nullable=False)
    assigned_to = Column(String(36), ForeignKey("users.user_id", ondelete="SET NULL"), nullable=True)
    status = Column(String(20), default="pending")  # ApprovalStatus
    resolved_at = Column(DateTime, nullable=True)
    comments = Column(Text, nullable=True)

    # Relationships
    audit_event = relationship("AuditEvent", back_populates="hitl_approvals")
    assigned_user = relationship("User", back_populates="hitl_approvals")


# ===========================================================================
# 4.6 Experience & Feedback (Layer 8)
# ===========================================================================

class Feedback(Base):
    """
    User feedback logs table per Doc 9 Section 4.6.
    """
    __tablename__ = "feedback"

    feedback_id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(String(36), nullable=False)
    turn_id = Column(String(36), ForeignKey("conversation_turns.turn_id", ondelete="CASCADE"), nullable=True)
    rating = Column(Integer, nullable=False)  # -1 | 0 | 1
    correction_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    turn = relationship("ConversationTurn", back_populates="feedback_entries")


class UsageMetric(Base):
    """
    Tenant daily usage aggregates table per Doc 9 Section 4.6.
    Used to drive dash displays and calculate cost thresholds.
    """
    __tablename__ = "usage_metrics"

    metric_id = Column(String(36), primary_key=True, default=new_uuid_str)
    tenant_id = Column(String(36), nullable=False)
    metric_date = Column(Date, nullable=False)
    token_count = Column(Integer, default=0)
    request_count = Column(Integer, default=0)
    automation_count = Column(Integer, default=0)
    cost_usd = Column(Numeric(12, 4), default=0.0)

    __table_args__ = (
        Index("uq_tenant_metric_date", "tenant_id", "metric_date", unique=True),
    )


# ===========================================================================
# IMMUTABILITY & AUDIT ENFORCEMENT
# ===========================================================================

# Enforces that no records in audit_events are modified or deleted at the ORM level
@event.listens_for(AuditEvent, "before_update")
def block_audit_update(mapper, connection, target):
    raise PermissionError("Write blocked: audit_events table is append-only.")


@event.listens_for(AuditEvent, "before_delete")
def block_audit_delete(mapper, connection, target):
    raise PermissionError("Write blocked: audit_events table is append-only.")
