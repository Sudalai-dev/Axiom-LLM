"""Admin routes — governance policy authoring and user onboarding."""

from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.middleware.auth import resolve_security_context
from core.models.base import RequestContext
from core.security import verify_rbac
from storage.database import AsyncSessionLocal
from storage.models import Policy, User

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


class PolicyCreateRequest(BaseModel):
    name: str
    rule_definition: Dict[str, Any]
    risk_threshold: float = 0.7


class UserCreateRequest(BaseModel):
    name: str
    industry: str = "general"
    isolation_mode: str = "shared"


@router.post("/policies")
async def create_policy(
    req: PolicyCreateRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Creates a new governance policy rule for the caller's user."""
    verify_rbac(req_ctx.user.role, "configure_policies")
    import json

    async with AsyncSessionLocal() as db:
        policy = Policy(
            user_id=req_ctx.user.user_id,
            name=req.name,
            rule_definition=json.dumps(req.rule_definition),
            risk_threshold=req.risk_threshold,
        )
        db.add(policy)
        await db.commit()
        return {"policy_id": policy.policy_id, "name": policy.name}


@router.post("/users")
async def create_user(
    req: UserCreateRequest,
    req_ctx: RequestContext = Depends(resolve_security_context),
):
    """Onboards a new user. Platform admin only."""
    verify_rbac(req_ctx.user.role, "manage_users")
    async with AsyncSessionLocal() as db:
        user = User(name=req.name, industry=req.industry, isolation_mode=req.isolation_mode)
        db.add(user)
        await db.commit()
        return {"user_id": user.user_id, "name": user.name}
