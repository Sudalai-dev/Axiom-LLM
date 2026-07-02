"""
Layer 4 — Enriched Context Contract.

Defines the canonical output of the Knowledge Enrichment Layer (L4).
The EnrichedContext payload encapsulates the context frame together with 
the retrieved chunks, hybrid search stats, knowledge graph relations, 
and citation references.

Traces to:
  - Document 7 (LLD) Section 5: Knowledge Layer contract
  - Document 11 (RAG Design) Section 4: Retrieval parameters & no-grounding handling
  - Document 11 (RAG Design) Section 5: Citation attachment schema
  - Document 7 (LLD) Section 11: Inter-layer events (EnrichedContext)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import Field

from axiom.core.models.base import (
    OCIFBaseModel, RequestContext, SourceType, new_uuid, utc_now,
)
from axiom.core.models.context import ContextFrame


class GroundedChunk(OCIFBaseModel):
    """
    A single retrieved grounding chunk per Doc 11 Section 5.
    
    Carries complete source and tracking references required to attach
    accurate user-facing citations.
    """
    chunk_id: str = Field(..., description="UUID of the individual chunk")
    doc_id: str = Field(..., description="UUID of parent document resource")
    title: str = Field(..., description="Document filename or title")
    section_ref: str = Field(default="General", description="Section header where the chunk resides")
    text: str = Field(..., description="Grounding text content of this chunk")
    score: float = Field(..., description="Fitted fusion retrieval score (RRF or similarity)")
    source_type: SourceType = Field(default=SourceType.UPLOAD, description="upload | api | database | web")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadata tags (author, modified, etc.)")


class EnrichedContext(OCIFBaseModel):
    """
    Canonical output of Layer 4 — Knowledge Enrichment (RAG).

    Contains the query context frame augmented with semantic vector/lexical retrieval
    information, graph-traversal relations, confidence metrics, and grounding states.

    Per Doc 7 Section 5 and Doc 11:
    - Grounded chunks with source citations
    - Hybrid vector + keyword retrieval results
    - No-grounding detection (similarity score threshold logic)
    - Knowledge Graph entity-relationships
    """
    context_id: str = Field(default_factory=new_uuid, description="Unique enriched context ID")
    timestamp: datetime = Field(default_factory=utc_now)

    # Retrieval status indicators
    retrieval_confidence: float = Field(default=0.0, description="Confidence of the retrieval grounding (0.0-1.0)")
    no_grounding_found: bool = Field(default=True, description="True if no chunks exceeded similarity threshold")

    # Grounding resources
    retrieved_chunks: List[GroundedChunk] = Field(default_factory=list, description="Grounding context chunks")
    kg_relations: List[str] = Field(default_factory=list, description="Extracted entity relationships from Graph DB")

    # Upstream layers & request contexts
    context_frame: ContextFrame = Field(..., description="Originating context frame")
    request_context: RequestContext = Field(..., description="Request execution metadata envelope")
