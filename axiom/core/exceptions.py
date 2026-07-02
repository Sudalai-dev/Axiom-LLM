"""
OCIF Platform Exception Hierarchy & RFC 7807 Error Model.

All API errors conform to RFC 7807 Problem Details format
as specified in Document 10 Section 8. Each exception maps to
a specific HTTP status code and problem type URI.

Traces to:
  - Document 10 (API Specification) Section 8: Error Format
  - Document 7 (Low Level Design) Section 12: Design invariants
  - Document 14 (Security Design) Section 2: Fail-closed principle
"""

import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# RFC 7807 Problem Details model
# ---------------------------------------------------------------------------

@dataclass
class ProblemDetail:
    """
    RFC 7807 Problem Details response body.

    Per Document 10 Section 8, all error responses include:
    - type: A URI identifying the problem type
    - title: Short human-readable summary
    - status: HTTP status code
    - detail: Full explanation
    - correlation_id: Request trace ID for observability
    """
    type: str
    title: str
    status: int
    detail: str
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    instance: Optional[str] = None
    extensions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "correlation_id": self.correlation_id,
        }
        if self.instance:
            result["instance"] = self.instance
        if self.extensions:
            result.update(self.extensions)
        return result


# ---------------------------------------------------------------------------
# Base OCIF Exception
# ---------------------------------------------------------------------------

class OCIFError(Exception):
    """Base exception for all OCIF platform errors."""

    def __init__(
        self,
        detail: str,
        status_code: int = 500,
        problem_type: str = "https://ocif-platform.dev/errors/internal",
        title: str = "Internal Server Error",
        correlation_id: Optional[str] = None,
        extensions: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.detail = detail
        self.status_code = status_code
        self.problem_type = problem_type
        self.title = title
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.extensions = extensions or {}
        super().__init__(detail)

    def to_problem_detail(self) -> ProblemDetail:
        return ProblemDetail(
            type=self.problem_type,
            title=self.title,
            status=self.status_code,
            detail=self.detail,
            correlation_id=self.correlation_id,
            extensions=self.extensions,
        )


# ---------------------------------------------------------------------------
# Authentication & Authorization Errors (Doc 14 Section 3)
# ---------------------------------------------------------------------------

class AuthenticationError(OCIFError):
    """Raised when authentication fails — invalid/expired JWT, missing token."""

    def __init__(self, detail: str = "Authentication required", correlation_id: Optional[str] = None) -> None:
        super().__init__(
            detail=detail,
            status_code=401,
            problem_type="https://ocif-platform.dev/errors/authentication-failed",
            title="Authentication Failed",
            correlation_id=correlation_id,
        )


class AuthorizationError(OCIFError):
    """Raised when the authenticated user lacks the required role/permission."""

    def __init__(
        self,
        detail: str = "Insufficient permissions",
        required_role: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        extensions = {}
        if required_role:
            extensions["required_role"] = required_role
        super().__init__(
            detail=detail,
            status_code=403,
            problem_type="https://ocif-platform.dev/errors/authorization-denied",
            title="Authorization Denied",
            correlation_id=correlation_id,
            extensions=extensions,
        )


# ---------------------------------------------------------------------------
# Tenant Errors (Doc 9 Section 3)
# ---------------------------------------------------------------------------

class TenantNotFoundError(OCIFError):
    """Raised when the tenant cannot be resolved from the JWT claims."""

    def __init__(self, detail: str = "Tenant not found or not accessible", correlation_id: Optional[str] = None) -> None:
        super().__init__(
            detail=detail,
            status_code=404,
            problem_type="https://ocif-platform.dev/errors/tenant-not-found",
            title="Tenant Not Found",
            correlation_id=correlation_id,
        )


class TenantIsolationError(OCIFError):
    """Raised when a cross-tenant data access attempt is detected."""

    def __init__(self, detail: str = "Cross-tenant access violation detected", correlation_id: Optional[str] = None) -> None:
        super().__init__(
            detail=detail,
            status_code=403,
            problem_type="https://ocif-platform.dev/errors/tenant-isolation-violation",
            title="Tenant Isolation Violation",
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# Rate Limiting (Doc 10 Section 9)
# ---------------------------------------------------------------------------

class RateLimitExceededError(OCIFError):
    """Raised when a tenant exceeds their rate limit tier."""

    def __init__(
        self,
        detail: str = "Rate limit exceeded",
        retry_after_seconds: int = 60,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            detail=detail,
            status_code=429,
            problem_type="https://ocif-platform.dev/errors/rate-limit-exceeded",
            title="Rate Limit Exceeded",
            correlation_id=correlation_id,
            extensions={"retry_after_seconds": retry_after_seconds},
        )


# ---------------------------------------------------------------------------
# Policy & Governance Errors — Layer 7 (Doc 7 Section 12, Doc 14 Section 6)
# ---------------------------------------------------------------------------

class PolicyViolationError(OCIFError):
    """
    Raised when a proposed action violates a policy rule.

    Per Doc 14 Section 6: policies are rules-as-code evaluated deterministically.
    Default-deny posture — an action is blocked unless it explicitly matches an
    allow rule or falls under the auto-approval threshold.
    """

    def __init__(
        self,
        detail: str,
        violated_rules: Optional[List[str]] = None,
        risk_score: Optional[float] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        extensions: Dict[str, Any] = {}
        if violated_rules:
            extensions["violated_rules"] = violated_rules
        if risk_score is not None:
            extensions["risk_score"] = risk_score
        super().__init__(
            detail=detail,
            status_code=422,
            problem_type="https://ocif-platform.dev/errors/policy-violation",
            title="Policy Violation",
            correlation_id=correlation_id,
            extensions=extensions,
        )


class GovernanceBlockedError(OCIFError):
    """
    Raised when the fail-closed invariant blocks an action due to
    ambiguous or malformed policy input.

    Per Doc 7 Section 12 Invariant 4: any failure in policy evaluation
    must result in a blocked action, not a default allow.
    """

    def __init__(
        self,
        detail: str = "Action blocked by governance — fail-closed invariant triggered",
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            detail=detail,
            status_code=422,
            problem_type="https://ocif-platform.dev/errors/governance-blocked",
            title="Governance Block — Fail-Closed",
            correlation_id=correlation_id,
        )


class HITLRequiredError(OCIFError):
    """Raised when an action requires human-in-the-loop approval."""

    def __init__(
        self,
        detail: str = "Action requires human approval",
        approval_id: Optional[str] = None,
        risk_score: Optional[float] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        extensions: Dict[str, Any] = {}
        if approval_id:
            extensions["approval_id"] = approval_id
        if risk_score is not None:
            extensions["risk_score"] = risk_score
        super().__init__(
            detail=detail,
            status_code=202,
            problem_type="https://ocif-platform.dev/errors/hitl-required",
            title="Human Approval Required",
            correlation_id=correlation_id,
            extensions=extensions,
        )


# ---------------------------------------------------------------------------
# Knowledge / RAG Errors — Layer 4 (Doc 11)
# ---------------------------------------------------------------------------

class NoGroundingFoundError(OCIFError):
    """
    Raised when retrieval returns no chunks above the similarity threshold.

    Per Doc 11 Section 4.3: pipeline returns retrieval_confidence=0 and
    no_grounding_found=true. The response must disclose the absence of grounding.
    """

    def __init__(self, detail: str = "No relevant knowledge grounding found for this query", correlation_id: Optional[str] = None) -> None:
        super().__init__(
            detail=detail,
            status_code=200,  # Not an error per se — valid response with no grounding
            problem_type="https://ocif-platform.dev/errors/no-grounding",
            title="No Grounding Found",
            correlation_id=correlation_id,
            extensions={"no_grounding_found": True, "retrieval_confidence": 0.0},
        )


class IngestionError(OCIFError):
    """Raised when document ingestion fails."""

    def __init__(self, detail: str, correlation_id: Optional[str] = None) -> None:
        super().__init__(
            detail=detail,
            status_code=422,
            problem_type="https://ocif-platform.dev/errors/ingestion-failed",
            title="Document Ingestion Failed",
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# LLM / Cognition Errors — Layer 6 (Doc 10 Section 6)
# ---------------------------------------------------------------------------

class LLMProviderError(OCIFError):
    """Raised when the primary LLM provider fails and fallback is exhausted."""

    def __init__(
        self,
        detail: str,
        provider: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        extensions = {}
        if provider:
            extensions["failed_provider"] = provider
        super().__init__(
            detail=detail,
            status_code=502,
            problem_type="https://ocif-platform.dev/errors/llm-provider-failure",
            title="LLM Provider Failure",
            correlation_id=correlation_id,
            extensions=extensions,
        )


class LLMTimeoutError(OCIFError):
    """Raised when an LLM request exceeds the configured timeout."""

    def __init__(self, detail: str = "LLM inference request timed out", provider: Optional[str] = None, correlation_id: Optional[str] = None) -> None:
        extensions = {}
        if provider:
            extensions["failed_provider"] = provider
        super().__init__(
            detail=detail,
            status_code=504,
            problem_type="https://ocif-platform.dev/errors/llm-timeout",
            title="LLM Timeout",
            correlation_id=correlation_id,
            extensions=extensions,
        )


# ---------------------------------------------------------------------------
# Agent / Orchestration Errors — Layer 5 (Doc 13)
# ---------------------------------------------------------------------------

class AgentMaxStepsExceededError(OCIFError):
    """
    Raised when an agent plan exceeds the max-step guard.

    Per Doc 13 Section 8: max-step guard (configurable, default 15 steps)
    forces termination with partial result.
    """

    def __init__(
        self,
        detail: str = "Agent exceeded maximum allowed steps",
        max_steps: int = 15,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            detail=detail,
            status_code=422,
            problem_type="https://ocif-platform.dev/errors/agent-max-steps",
            title="Agent Step Limit Exceeded",
            correlation_id=correlation_id,
            extensions={"max_steps": max_steps},
        )


class ToolInvocationError(OCIFError):
    """Raised when a tool invocation fails within the agent runtime."""

    def __init__(
        self,
        detail: str,
        tool_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        extensions = {}
        if tool_id:
            extensions["tool_id"] = tool_id
        super().__init__(
            detail=detail,
            status_code=502,
            problem_type="https://ocif-platform.dev/errors/tool-invocation-failed",
            title="Tool Invocation Failed",
            correlation_id=correlation_id,
            extensions=extensions,
        )


# ---------------------------------------------------------------------------
# Audit Errors — Layer 7 (Doc 9 Section 4.5)
# ---------------------------------------------------------------------------

class AuditWriteError(OCIFError):
    """
    Raised when audit log write fails.

    Per Doc 18 Section 7: audit log write failure circuit-breaks action
    execution (fail-closed — no action without audit).
    """

    def __init__(self, detail: str = "Audit log write failed — action execution blocked", correlation_id: Optional[str] = None) -> None:
        super().__init__(
            detail=detail,
            status_code=500,
            problem_type="https://ocif-platform.dev/errors/audit-write-failure",
            title="Audit Log Write Failure",
            correlation_id=correlation_id,
        )


# ---------------------------------------------------------------------------
# Validation Errors
# ---------------------------------------------------------------------------

class ValidationError(OCIFError):
    """Raised for request payload validation failures."""

    def __init__(
        self,
        detail: str,
        field_errors: Optional[Dict[str, str]] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        extensions = {}
        if field_errors:
            extensions["field_errors"] = field_errors
        super().__init__(
            detail=detail,
            status_code=422,
            problem_type="https://ocif-platform.dev/errors/validation-failed",
            title="Validation Failed",
            correlation_id=correlation_id,
            extensions=extensions,
        )


class ResourceNotFoundError(OCIFError):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        correlation_id: Optional[str] = None,
    ) -> None:
        super().__init__(
            detail=f"{resource_type} with id '{resource_id}' not found",
            status_code=404,
            problem_type="https://ocif-platform.dev/errors/resource-not-found",
            title="Resource Not Found",
            correlation_id=correlation_id,
            extensions={"resource_type": resource_type, "resource_id": resource_id},
        )
