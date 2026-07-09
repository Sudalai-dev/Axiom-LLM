"""Auth routes — local single-tenant JWT login for the seeded admin account."""

from fastapi import APIRouter
from pydantic import BaseModel

from api.routes.deps import SEED_TENANT_ID, SEED_USER_ID, SEED_USERNAME
from core.exceptions import AuthenticationError
from core.security import create_access_token

router = APIRouter(prefix="/api/v1", tags=["Auth"])

_SEED_PASSWORD = "admin123"


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/auth/login", response_model=LoginResponse)
async def login(req: LoginRequest) -> LoginResponse:
    """Authenticates the seeded local admin account and returns a signed JWT."""
    if req.username != SEED_USERNAME or req.password != _SEED_PASSWORD:
        raise AuthenticationError("Invalid username or password")

    token = create_access_token({
        "sub": SEED_USERNAME,
        "user_id": SEED_USER_ID,
        "tenant_id": SEED_TENANT_ID,
        "tenant_name": "Default Tenant",
        "role": "platform_admin",
        "industry": "technology",
    })
    return LoginResponse(access_token=token)
