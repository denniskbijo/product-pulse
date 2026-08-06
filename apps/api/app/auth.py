from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings
from app.passwords import verify_password

Role = Literal["admin", "user"]

security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class AuthUser:
    username: str
    role: Role


def _configured_users(settings: Settings) -> dict[str, tuple[str, Role]]:
    """Map username → (bcrypt hash, role). Plaintext env passwords are not used."""
    users: dict[str, tuple[str, Role]] = {}
    if settings.admin_username and settings.admin_password_hash:
        users[settings.admin_username] = (settings.admin_password_hash, "admin")
    if settings.user_username and settings.user_password_hash:
        users[settings.user_username] = (settings.user_password_hash, "user")
    return users


def authenticate(username: str, password: str, settings: Settings) -> AuthUser | None:
    users = _configured_users(settings)
    entry = users.get(username)
    if entry is None:
        # Dummy verify to reduce username-enumeration timing differences.
        verify_password(
            password,
            "$2b$12$GGim1lb6UHAr8XshlH3J4OrvMKQLLKhANnRF6//m3ZU3PLhJmircG",
        )
        return None
    expected_hash, role = entry
    if not verify_password(password, expected_hash):
        return None
    return AuthUser(username=username, role=role)


def create_access_token(user: AuthUser, settings: Settings) -> str:
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured")
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, settings: Settings) -> AuthUser:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured",
        )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    username = payload.get("sub")
    role = payload.get("role")
    if not username or role not in ("admin", "user"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    return AuthUser(username=str(username), role=role)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return decode_token(credentials.credentials, settings)


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user
