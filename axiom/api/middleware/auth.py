"""
OCIF Auth Middleware & Dependencies — Layer 2.

Handles JWT parsing, signature validation, tenant context binding, and security context
propagation to core observability and storage layers.

Traces to:
  - Document 6 (LLD) Section 2: API Gateway & Auth Service
  - Document 14 (Security Design) Section 3: Identity & Access Management
  - Document 10 (API Specification) Section 1: API Design Principles
"""

from fastapi import Request, Depends, Header
from typing import Dict, Any, Optional

from core.exceptions import AuthenticationError, TenantNotFoundError
from core.security import decode_access_token
from core.models.base import UserContext, TenantContext, RequestContext, UserRole
from core.observability import RequestContextManager


async def extract_token_from_header(authorization: Optional[str] = Header(None)) -> str:
    """Extracts the Bearer token from the Authorization header."""
    if not authorization:
        raise AuthenticationError("Missing Authorization header")
        
    if not authorization.startswith("Bearer "):
        raise AuthenticationError("Authorization header must use Bearer scheme")
        
    return authorization.replace("Bearer ", "")


async def resolve_security_context(request: Request, token: str = Depends(extract_token_from_header)) -> RequestContext:
    """
    FastAPI dependency that decodes the JWT token, resolves user and tenant contexts,
    and sets up the request correlation and logging envelopes.
    """
    # Extract correlation ID injected by gateway middleware
    correlation_id = request.headers.get("X-Correlation-ID") or request.state.correlation_id

    # Decode and validate JWT
    payload = decode_access_token(token)

    # Resolve tenant context from JWT claims
    tenant_id = payload.get("tenant_id")
    tenant_name = payload.get("tenant_name")
    if not tenant_id or not tenant_name:
        raise TenantNotFoundError("Tenant identifier missing in token claims")

    tenant_ctx = TenantContext(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        industry=payload.get("industry", "general"),
        isolation_mode=payload.get("isolation_mode", "shared"),
        rate_limit_tier=payload.get("rate_limit_tier", "standard"),
    )

    # Resolve user context from JWT claims
    user_id = payload.get("user_id")
    username = payload.get("sub")  # subject claim
    role_str = payload.get("role")
    
    if not user_id or not username or not role_str:
        raise AuthenticationError("Subject or role identity missing in token claims")

    try:
        user_role = UserRole(role_str)
    except ValueError:
        raise AuthenticationError(f"Token contains invalid role assignment: '{role_str}'")

    user_ctx = UserContext(
        user_id=user_id,
        username=username,
        role=user_role,
        tenant_id=tenant_id,
        department=payload.get("department"),
        permissions=payload.get("permissions", {}),
    )

    # Create RequestContext envelope
    req_ctx = RequestContext(
        correlation_id=correlation_id,
        session_id=request.headers.get("X-Session-ID"),
        tenant=tenant_ctx,
        user=user_ctx,
    )

    # Bind to request state
    request.state.request_context = req_ctx

    # Setup thread-local/task-local context for structured JSON logging
    logging_manager = RequestContextManager(
        correlation_id=correlation_id,
        tenant_id=tenant_id,
        user_id=user_id,
    )
    # Store logging manager in state to cleanup on request termination
    request.state.logging_manager = logging_manager
    logging_manager.__enter__()

    return req_ctx


async def get_request_context(request: Request) -> RequestContext:
    """Dependency to retrieve the pre-resolved security context envelope from request state."""
    if not hasattr(request.state, "request_context"):
        raise AuthenticationError("Security context not resolved")
    return request.state.request_context
