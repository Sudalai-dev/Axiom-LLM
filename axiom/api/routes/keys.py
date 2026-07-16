"""User API-key routes — manage a user's own provider keys (optional BYO-key).

Paid traffic is served by the platform's configured provider keys by default,
so supplying a key here is optional. When present, a key is stored encrypted at
rest (Fernet) and only its last 4 characters are ever returned — the plaintext
is never echoed back, listed, or logged.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select

from api.middleware.auth import resolve_security_context
from core.exceptions import ResourceNotFoundError, ValidationError
from core.models.base import RequestContext
from core.security import encrypt_secret, last4
from storage.database import AsyncSessionLocal
from storage.models import UserApiKey

router = APIRouter(prefix="/api/v1", tags=["Keys"])

_ALLOWED_PROVIDERS = {"openai", "claude", "gemini", "llama"}


class ApiKeyCreate(BaseModel):
    provider: str = Field(..., description="openai | claude | gemini | llama")
    api_key: str = Field(..., min_length=8, description="The provider secret (write-only)")


class ApiKeyView(BaseModel):
    provider: str
    last4: str
    created_at: Optional[str] = None


@router.get("/keys", response_model=List[ApiKeyView])
async def list_keys(req_ctx: RequestContext = Depends(resolve_security_context)) -> List[ApiKeyView]:
    """Lists the user's stored keys (metadata only — never the secret)."""
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(UserApiKey).filter(UserApiKey.user_id == req_ctx.user.user_id)
        )).scalars().all()
        return [
            ApiKeyView(
                provider=r.provider,
                last4=r.last4,
                created_at=r.created_at.isoformat() if r.created_at else None,
            )
            for r in rows
        ]


@router.post("/keys", response_model=ApiKeyView, status_code=201)
async def add_key(
    req: ApiKeyCreate,
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> ApiKeyView:
    """Stores (or replaces) the user's key for a provider, encrypted at rest."""
    provider = req.provider.lower().strip()
    if provider not in _ALLOWED_PROVIDERS:
        raise ValidationError(f"Unsupported provider '{req.provider}'. Allowed: {sorted(_ALLOWED_PROVIDERS)}")

    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(UserApiKey).filter(
                UserApiKey.user_id == req_ctx.user.user_id,
                UserApiKey.provider == provider,
            )
        )).scalars().first()

        tail = last4(req.api_key)
        ciphertext = encrypt_secret(req.api_key)

        if existing:
            existing.encrypted_key = ciphertext
            existing.last4 = tail
            row = existing
        else:
            row = UserApiKey(
                user_id=req_ctx.user.user_id,
                tenant_id=req_ctx.tenant.tenant_id,
                provider=provider,
                encrypted_key=ciphertext,
                last4=tail,
            )
            db.add(row)
        await db.commit()
        await db.refresh(row)
        return ApiKeyView(
            provider=row.provider,
            last4=row.last4,
            created_at=row.created_at.isoformat() if row.created_at else None,
        )


@router.delete("/keys/{provider}", status_code=204)
async def delete_key(
    provider: str,
    req_ctx: RequestContext = Depends(resolve_security_context),
) -> None:
    """Removes the user's stored key for a provider."""
    provider = provider.lower().strip()
    async with AsyncSessionLocal() as db:
        existing = (await db.execute(
            select(UserApiKey).filter(
                UserApiKey.user_id == req_ctx.user.user_id,
                UserApiKey.provider == provider,
            )
        )).scalars().first()
        if not existing:
            raise ResourceNotFoundError("api_key", provider)
        await db.execute(
            delete(UserApiKey).filter(
                UserApiKey.user_id == req_ctx.user.user_id,
                UserApiKey.provider == provider,
            )
        )
        await db.commit()
