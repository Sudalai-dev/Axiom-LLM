"""Auth routes — local account registration and hashed-password JWT login.

Replaces the previous single hardcoded admin/`admin123` check with real
accounts: each user is a row in the ``users`` table with a per-user salted
PBKDF2 credential, and every new account gets a ``free`` :class:`Subscription`
so the freemium quota applies from the first request. The seeded admin
(bootstrapped in ``api/routes/seed.py``) is the only pre-existing account; its
password comes from ``OCIF_ADMIN_PASSWORD`` (dev default ``admin123``), never a
literal in this handler.
"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from api.routes.deps import SEED_TENANT_ID
from core.exceptions import AuthenticationError, ValidationError
from core.models.base import UserRole
from core.security import create_access_token, hash_password, verify_password
from storage.database import AsyncSessionLocal
from storage.models import Subscription, Tenant, User

router = APIRouter(prefix="/api/v1", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    email: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    plan: str


async def _issue_token(db, user: User) -> LoginResponse:
    """Builds a signed JWT whose claims are sourced from the DB user/tenant."""
    tenant = (await db.execute(
        select(Tenant).filter(Tenant.tenant_id == user.tenant_id)
    )).scalars().first()
    subscription = (await db.execute(
        select(Subscription).filter(Subscription.user_id == user.user_id)
    )).scalars().first()

    token = create_access_token({
        "sub": user.external_idp_subject,
        "user_id": user.user_id,
        "tenant_id": user.tenant_id,
        "tenant_name": tenant.name if tenant else "Default Tenant",
        "role": user.role,
        "industry": (tenant.industry if tenant else None) or "technology",
    })
    return LoginResponse(
        access_token=token,
        role=user.role,
        plan=subscription.plan if subscription else "free",
    )


@router.post("/auth/register", response_model=LoginResponse, status_code=201)
async def register(req: RegisterRequest) -> LoginResponse:
    """Creates a new end-user account on the local tenant and logs it in.

    New accounts start on the ``free`` plan (daily OpenCode quota). Usernames
    are unique within the tenant.
    """
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(User).filter(
                User.tenant_id == SEED_TENANT_ID,
                User.external_idp_subject == req.username,
            )
        )).scalars().first()
        if existing:
            raise ValidationError(f"Username '{req.username}' is already taken")

        user = User(
            tenant_id=SEED_TENANT_ID,
            external_idp_subject=req.username,
            email=req.email,
            role=UserRole.END_USER.value,
            department=None,
            hashed_password=hash_password(req.password),
        )
        db.add(user)
        await db.flush()  # assign user.user_id before creating the subscription

        db.add(Subscription(
            user_id=user.user_id,
            tenant_id=SEED_TENANT_ID,
            plan="free",
            free_chats_used=0,
        ))
        await db.commit()
        await db.refresh(user)
        return await _issue_token(db, user)


@router.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    """Authenticates a local account by verifying its salted password hash."""
    async with AsyncSessionLocal() as db:
        user = (await db.execute(
            select(User).filter(
                User.tenant_id == SEED_TENANT_ID,
                User.external_idp_subject == req.username,
            )
        )).scalars().first()

        if not user or not user.hashed_password or not verify_password(req.password, user.hashed_password):
            # Uniform error — never disclose whether the username exists.
            raise AuthenticationError("Invalid username or password")

        return await _issue_token(db, user)
