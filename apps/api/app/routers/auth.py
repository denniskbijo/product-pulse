from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import AuthUser, authenticate, create_access_token, get_current_user
from app.config import Settings, get_settings
from app.db import get_db
from app.rate_limit import (
    assert_login_allowed,
    clear_login_failures,
    client_ip,
    record_login_failure,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class MeResponse(BaseModel):
    username: str
    role: str


@router.post("/login", response_model=LoginResponse)
def login(
    body: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="JWT_SECRET is not configured on the server",
        )
    if not settings.admin_password_hash and not settings.user_password_hash:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password hashes are not configured (set ADMIN_PASSWORD_HASH / USER_PASSWORD_HASH)",
        )

    ip = client_ip(request)
    username = body.username.strip()
    assert_login_allowed(db, ip=ip, username=username)

    user = authenticate(username, body.password, settings)
    if user is None:
        record_login_failure(db, ip=ip, username=username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    clear_login_failures(db, ip=ip, username=username)
    token = create_access_token(user, settings)
    return LoginResponse(
        access_token=token,
        username=user.username,
        role=user.role,
    )


@router.get("/me", response_model=MeResponse)
def me(user: AuthUser = Depends(get_current_user)) -> MeResponse:
    return MeResponse(username=user.username, role=user.role)
