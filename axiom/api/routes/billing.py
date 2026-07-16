"""Billing routes — upgrade status, checkout, webhook, and admin activation.

Bridges the pluggable payment provider (``billing/``) to the entitlement state
machine (``core/entitlement.py``). A successful payment (or an admin grant)
calls :meth:`EntitlementService.mark_paid`, flipping the user to the paid plan
so the freemium cap no longer applies.
"""

from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.middleware.auth import resolve_security_context
from api.routes.deps import SEED_TENANT_ID, entitlement, is_developer
from billing import get_payment_provider
from core.exceptions import AuthorizationError, ResourceNotFoundError
from core.models.base import RequestContext
from storage.database import AsyncSessionLocal
from storage.models import User

router = APIRouter(prefix="/api/v1", tags=["Billing"])


class CheckoutResponse(BaseModel):
    provider: str
    mode: str
    checkout_url: Optional[str] = None
    message: Optional[str] = None
    activated: bool = False


class GrantRequest(BaseModel):
    username: str = Field(..., description="Target account to activate/deactivate")
    plan: str = Field("paid", description="paid | free")


def _role(req_ctx: RequestContext) -> str:
    role = req_ctx.user.role
    return role.value if hasattr(role, "value") else str(role)


@router.get("/billing/status")
async def billing_status(req_ctx: RequestContext = Depends(resolve_security_context)):
    """Returns the caller's plan, remaining free quota, renewal time, and price."""
    status = await entitlement.get_status(
        req_ctx.user.user_id, req_ctx.tenant.tenant_id, _role(req_ctx)
    )
    status["payment_provider"] = get_payment_provider().name
    return status


@router.post("/billing/checkout", response_model=CheckoutResponse)
async def billing_checkout(req_ctx: RequestContext = Depends(resolve_security_context)) -> CheckoutResponse:
    """Starts an upgrade via the configured payment provider."""
    provider = get_payment_provider()
    result = await provider.create_checkout(
        user_id=req_ctx.user.user_id,
        tenant_id=req_ctx.tenant.tenant_id,
        email=None,
    )
    return CheckoutResponse(
        provider=result.provider,
        mode=result.mode,
        checkout_url=result.checkout_url,
        message=result.message,
        activated=result.activated,
    )


@router.post("/billing/webhook")
async def billing_webhook(request: Request):
    """Async payment-provider callback (e.g. Stripe). Grants access on success.

    Unauthenticated by design (called by the provider, verified by signature).
    """
    provider = get_payment_provider()
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    result = await provider.handle_webhook(payload, signature)
    if result and result.paid:
        # Resolve the user's tenant to scope the entitlement update.
        async with AsyncSessionLocal() as db:
            user = (await db.execute(
                select(User).filter(User.user_id == result.user_id)
            )).scalars().first()
        if user:
            await entitlement.mark_paid(result.user_id, user.tenant_id)
    return {"received": True}


@router.post("/billing/admin/grant")
async def billing_admin_grant(
    req: GrantRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Admin-only: activate (or revoke) a user's paid plan.

    This is the manual payment path — an operator flips an account to paid
    after an out-of-band payment/invoice. Restricted to platform admins.
    """
    if not is_developer(req_ctx):
        raise AuthorizationError("Only platform admins may grant paid plans")

    async with AsyncSessionLocal() as db:
        user = (await db.execute(
            select(User).filter(
                User.tenant_id == SEED_TENANT_ID,
                User.external_idp_subject == req.username,
            )
        )).scalars().first()
    if not user:
        raise ResourceNotFoundError("user", req.username)

    if req.plan.lower() == "free":
        await entitlement.mark_free(user.user_id, user.tenant_id)
    else:
        await entitlement.mark_paid(user.user_id, user.tenant_id)

    return await entitlement.get_status(user.user_id, user.tenant_id, user.role)
