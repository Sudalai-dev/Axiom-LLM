"""
Layer 1 — Perception Event Contract.

Defines the canonical output of the Perception Layer (L1).
The PerceptionEvent is the first structured representation of any input
to the OCIF platform — text, document upload, or API-sourced data.

Traces to:
  - Document 7 (LLD) Section 2: Perception Layer contract
  - Document 7 (LLD) Section 11: Inter-layer events (PerceptionEvent)
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import Field

from axiom.core.models.base import OCIFBaseModel, new_uuid, utc_now


class InputAttachment(OCIFBaseModel):
    """An attachment uploaded alongside a text message."""
    attachment_id: str = Field(default_factory=new_uuid)
    type: str = Field(..., description="document | image | audio | video")
    uri: str = Field(..., description="Storage URI or upload reference")
    mime_type: Optional[str] = Field(default=None)
    size_bytes: Optional[int] = Field(default=None)


class PerceptionEvent(OCIFBaseModel):
    """
    Canonical output of Layer 1 — Perception.

    Represents a normalized, validated, and classified raw input.
    Consumed by Layer 2 (Capture/Gateway) to create a CaptureEvent.

    Per Doc 7 Section 2:
    - Input validation (encoding, size, format)
    - Input type classification (text, document, api_data)
    - Security boundary check (injection pattern detection)
    - Language detection
    """
    event_id: str = Field(default_factory=new_uuid, description="Unique perception event ID")
    timestamp: datetime = Field(default_factory=utc_now)

    # Raw input data
    raw_text: str = Field(..., description="Original text input or extracted text from attachment")
    input_type: str = Field(default="text", description="text | document | image | api_data")
    attachments: List[InputAttachment] = Field(default_factory=list)

    # Perception analysis results
    language_detected: str = Field(default="en", description="ISO 639-1 language code")
    encoding_valid: bool = Field(default=True, description="Whether input encoding is valid UTF-8")
    input_length_tokens: int = Field(default=0, description="Approximate token count")

    # Security screening
    security_flags: List[str] = Field(default_factory=list, description="Detected security concerns (injection patterns, etc.)")
    is_safe: bool = Field(default=True, description="False if security screening detected threats")
    rejection_reason: Optional[str] = Field(default=None, description="Reason for rejection if is_safe=False")

    # Metadata
    source_channel: str = Field(default="chat", description="chat | api | webhook | workflow")
    client_metadata: Dict[str, Any] = Field(default_factory=dict, description="Client-provided metadata")
