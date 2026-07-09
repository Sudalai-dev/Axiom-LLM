"""Admin routes — governance policy authoring and tenant onboarding."""

from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.middleware.auth import resolve_security_context
from core.models.base import RequestContext
from core.security import verify_rbac
from storage.database import AsyncSessionLocal
from storage.models import Policy, Tenant

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


class PolicyCreateRequest(BaseModel):
    name: str
    rule_definition: Dict[str, Any]
    risk_threshold: float = 0.7


class TenantCreateRequest(BaseModel):
    name: str
    industry: str = "general"
    isolation_mode: str = "shared"


@router.post("/policies")
async def create_policy(
    req: PolicyCreateRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Creates a new governance policy rule for the caller's tenant."""
    verify_rbac(req_ctx.user.role, "configure_policies")
    import json

    async with AsyncSessionLocal() as db:
        policy = Policy(
            tenant_id=req_ctx.tenant.tenant_id,
            name=req.name,
            rule_definition=json.dumps(req.rule_definition),
            risk_threshold=req.risk_threshold,
        )
        db.add(policy)
        await db.commit()
        return {"policy_id": policy.policy_id, "name": policy.name}


@router.post("/tenants")
async def create_tenant(
    req: TenantCreateRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Onboards a new tenant. Platform admin only."""
    verify_rbac(req_ctx.user.role, "manage_tenants")
    async with AsyncSessionLocal() as db:
        tenant = Tenant(name=req.name, industry=req.industry, isolation_mode=req.isolation_mode)
        db.add(tenant)
        await db.commit()
        return {"tenant_id": tenant.tenant_id, "name": tenant.name}
