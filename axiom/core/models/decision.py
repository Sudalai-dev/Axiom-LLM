"""
Layer 7 — Decision Record Contract.

Defines the PolicyCheck model used by the Policy Engine.
"""

from typing import Optional
from pydantic import Field

from core.models.base import OCIFBaseModel, PolicyCheckResult


class PolicyCheck(OCIFBaseModel):
    """
    A single policy rule evaluation result.
    Deterministic checks per Doc 14 Section 6.
    """
    rule_name: str = Field(..., description="Unique code identifier of policy rule evaluated")
    result: PolicyCheckResult = Field(..., description="pass | fail")
    description: str = Field(..., description="Policy description")
    error_message: Optional[str] = Field(default=None, description="Detailed failure reason if result=fail")
