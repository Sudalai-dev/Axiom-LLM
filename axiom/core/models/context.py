"""
Layer 3 — Context Frame Contract.

Defines the canonical output of the Context Intelligence Layer (L3).
The ContextFrame integrates the raw input with resolved intent, entities, 
conversation memory, and system-injected heuristics.

Traces to:
  - Document 6 (LLD) Section 3: Context Intelligence Service
  - Document 7 (LLD) Section 4: Context Layer contract
  - Document 7 (LLD) Section 11: Inter-layer events (ContextFrame)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import Field

from axiom.core.models.base import (
    OCIFBaseModel, RequestContext, new_uuid, utc_now,
)
from axiom.core.models.capture import CaptureEvent


class EntityInfo(OCIFBaseModel):
    """Extracted Named Entity (NER) info per Doc 6 Section 3.1."""
    term: str = Field(..., description="The matched entity string")
    type: str = Field(..., description="Entity category (Protocol, Service, Database, DevOps, etc.)")
    confidence: float = Field(default=1.0, description="Extraction confidence score")


class MemoryTurn(OCIFBaseModel):
    """A single turn inside the conversation session history."""
    role: str = Field(..., description="user | assistant | system")
    content: str = Field(..., description="Text content of the turn")
    timestamp: datetime = Field(default_factory=utc_now)


class ConversationMemory(OCIFBaseModel):
    """Contextual conversation history compile payload."""
    turns: List[MemoryTurn] = Field(default_factory=list)
    is_compacted: bool = Field(default=False, description="True if history was summarized per turn limit rule")
    summary: Optional[str] = Field(default=None, description="Compacted session summary")


class ContextFrame(OCIFBaseModel):
    """
    Canonical output of Layer 3 — Context Intelligence.

    Contains intent analysis, named entities, conversation session history,
    user/tenant properties, and injected heuristics.

    Per Doc 6 Section 3 and Doc 7 Section 4:
    - Intent classification (lexical + semantic evaluation)
    - Named Entity Recognition (NER)
    - Conversation memory retrieval & compaction
    - Request context tracking
    """
    frame_id: str = Field(default_factory=new_uuid, description="Unique context frame ID")
    timestamp: datetime = Field(default_factory=utc_now)

    # Context intelligence metadata
    intent: str = Field(..., description="Classified intent (CodeGen, ArchitectureReview, GeneralQ&A, etc.)")
    intent_confidence: float = Field(default=1.0, description="Intent classification confidence (0.0-1.0)")
    requires_clarification: bool = Field(default=False, description="True if classification confidence is low")
    
    entities: List[EntityInfo] = Field(default_factory=list, description="Extracted technology terms & metadata")
    memory: ConversationMemory = Field(..., description="Session-bound memory representation")
    
    # System and domain heuristics
    system_constraints: List[str] = Field(default_factory=list, description="System boundary constraints")
    injected_heuristics: List[str] = Field(default_factory=list, description="Rule-based prompt styling heuristics")

    # Request envelope
    request_context: RequestContext = Field(..., description="Gateway request envelope context")
