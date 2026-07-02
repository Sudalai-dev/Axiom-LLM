"""
Layer 8 — Feedback Event Contract.

Defines the user feedback event payload collected at Layer 8 (Experience).
Used to evaluate response quality, record user corrections, and flag turns
as candidates for the offline training loop.

Traces to:
  - Document 10 (API Specification) Section 2.2: Feedback API contract
  - Document 7 (LLD) Section 9: Experience Layer contract
  - Document 7 (LLD) Section 11: Inter-layer events (FeedbackEvent)
"""

from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import Field

from axiom.core.models.base import (
    OCIFBaseModel, RequestContext, new_uuid, utc_now,
)
from axiom.core.models.decision import DecisionRecord


class FeedbackEvent(OCIFBaseModel):
    """
    Canonical output of Layer 8 — Experience.

    Contains user satisfaction metrics, ratings, corrected texts, and linking
    metadata to associate feedback with specific decision and request runs.

    Per Doc 10 Section 2.2 and Doc 7 Section 9:
    - User thumbs-up/down ratings
    - User-suggested correct answer texts
    - Association to system audit logs and request correlation IDs
    """
    feedback_id: str = Field(default_factory=new_uuid, description="Unique feedback event ID")
    timestamp: datetime = Field(default_factory=utc_now)

    # User satisfaction inputs
    turn_id: str = Field(..., description="UUID of the chat message turn being rated")
    rating: int = Field(..., description="User feedback score: -1 (poor), 0 (neutral), 1 (good)")
    correction_text: Optional[str] = Field(default=None, description="Corrected text suggested by user")

    # Offline training loop evaluation flag
    is_training_candidate: bool = Field(default=False, description="True if feedback indicates failure and maps to training queue")

    # Upstream layers & request contexts
    decision_record: DecisionRecord = Field(..., description="Associated platform decision record data")
    request_context: RequestContext = Field(..., description="Request execution metadata envelope")
