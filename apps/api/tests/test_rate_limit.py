from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import LoginThrottle
from app.rate_limit import (
    MAX_ATTEMPTS,
    assert_login_allowed,
    clear_login_failures,
    record_login_failure,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_login_rate_limit_blocks_after_max_failures():
    db = _session()
    ip = "1.2.3.4"
    username = "admin"
    for _ in range(MAX_ATTEMPTS):
        assert_login_allowed(db, ip=ip, username=username)
        record_login_failure(db, ip=ip, username=username)
    with pytest.raises(HTTPException) as exc:
        assert_login_allowed(db, ip=ip, username=username)
    assert exc.value.status_code == 429


def test_clear_login_failures_resets_window():
    db = _session()
    ip = "9.9.9.9"
    username = "basil"
    for _ in range(MAX_ATTEMPTS):
        record_login_failure(db, ip=ip, username=username)
    clear_login_failures(db, ip=ip, username=username)
    assert_login_allowed(db, ip=ip, username=username)


def test_expired_window_resets_on_next_failure():
    db = _session()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    db.add(
        LoginThrottle(
            key="ip:8.8.8.8",
            attempt_count=MAX_ATTEMPTS,
            window_started_at=past,
            blocked_until=past,
        )
    )
    db.commit()
    record_login_failure(db, ip="8.8.8.8", username="x")
    row = db.get(LoginThrottle, "ip:8.8.8.8")
    assert row is not None
    assert row.attempt_count == 1
    assert_login_allowed(db, ip="8.8.8.8", username="x")
