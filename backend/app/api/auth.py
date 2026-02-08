"""Authentication: JWT-based basic auth with seeded users."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

# ── Seed users ────────────────────────────────────────────────────────

SEED_USERS: dict[str, dict[str, Any]] = {
    "admin": {
        "id": "admin",
        "username": "admin",
        "password_hash": bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode(),
        "role": "admin",
        "display_name": "Administrator",
    },
    "user": {
        "id": "user",
        "username": "user",
        "password_hash": bcrypt.hashpw(b"user", bcrypt.gensalt()).decode(),
        "role": "user",
        "display_name": "Test User",
    },
}


# ── JWT helpers ───────────────────────────────────────────────────────

def create_token(user_id: str, username: str, role: str) -> str:
    settings = get_settings()
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


# ── Dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict[str, Any]:
    """Require a valid JWT. Returns the decoded token payload."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return decode_token(credentials.credentials)


async def require_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """Require the current user to have admin role."""
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ── Routes ────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user: dict[str, Any]


class UserInfo(BaseModel):
    id: str
    username: str
    role: str
    display_name: str


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest):
    """Authenticate with username/password, returns JWT."""
    user = SEED_USERS.get(req.username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not bcrypt.checkpw(req.password.encode(), user["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token(user["id"], user["username"], user["role"])

    return LoginResponse(
        token=token,
        user={
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "display_name": user["display_name"],
        },
    )


@router.get("/me", response_model=UserInfo)
async def get_me(user: dict[str, Any] = Depends(get_current_user)):
    """Get the current authenticated user."""
    seed = SEED_USERS.get(user.get("username", ""))
    return UserInfo(
        id=user["sub"],
        username=user["username"],
        role=user["role"],
        display_name=seed["display_name"] if seed else user["username"],
    )
