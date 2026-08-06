"""Simple DB-backed login rate limiting (works across serverless instances)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import LoginThrottle

# 10 attempts / 15 minutes per IP or per username key.
WINDOW_SECONDS = 15 * 60
MAX_ATTEMPTS = 10


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:128] or "unknown"
    if request.client and request.client.host:
        return request.client.host[:128]
    return "unknown"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    """SQLite often returns naive datetimes; normalize for comparisons."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _get_row(db: Session, key: str) -> LoginThrottle | None:
    return db.scalar(select(LoginThrottle).where(LoginThrottle.key == key))


def assert_login_allowed(db: Session, *, ip: str, username: str) -> None:
    """Raise 429 if IP or username is over the attempt budget."""
    now = _utcnow()
    for key in (f"ip:{ip}", f"user:{username.strip().lower()}"):
        row = _get_row(db, key)
        if row is None:
            continue
        blocked_until = _as_utc(row.blocked_until)
        if blocked_until and blocked_until > now:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again in a few minutes.",
            )
        started = _as_utc(row.window_started_at)
        assert started is not None
        window_end = started + timedelta(seconds=WINDOW_SECONDS)
        if row.attempt_count >= MAX_ATTEMPTS and now < window_end:
            row.blocked_until = window_end
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again in a few minutes.",
            )


def record_login_failure(db: Session, *, ip: str, username: str) -> None:
    now = _utcnow()
    for key in (f"ip:{ip}", f"user:{username.strip().lower()}"):
        row = _get_row(db, key)
        if row is None:
            db.add(
                LoginThrottle(
                    key=key,
                    attempt_count=1,
                    window_started_at=now,
                    blocked_until=None,
                )
            )
            continue
        started = _as_utc(row.window_started_at)
        assert started is not None
        window_end = started + timedelta(seconds=WINDOW_SECONDS)
        if now >= window_end:
            row.attempt_count = 1
            row.window_started_at = now
            row.blocked_until = None
        else:
            row.attempt_count += 1
            if row.attempt_count >= MAX_ATTEMPTS:
                row.blocked_until = window_end
    db.commit()


def clear_login_failures(db: Session, *, ip: str, username: str) -> None:
    keys = [f"ip:{ip}", f"user:{username.strip().lower()}"]
    db.execute(delete(LoginThrottle).where(LoginThrottle.key.in_(keys)))
    db.commit()
