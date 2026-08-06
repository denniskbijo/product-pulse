"""Oxylabs credit budget for Winter Hunt UI / soft gating."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import HuntRun
from app.providers.discovery.oxylabs import OxylabsClient, oxylabs_configured


def current_month_key(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    return stamp.strftime("%Y-%m")


def local_hunt_credits_used(db: Session, *, month_key: str) -> int:
    """Sum successful hunt Oxylabs requests recorded locally this month."""
    rows = db.execute(
        select(HuntRun.credits_used, HuntRun.started_at).where(
            HuntRun.status == "success",
            HuntRun.credits_used > 0,
        )
    ).all()
    total = 0
    for credits, started in rows:
        if started is None:
            continue
        key = started.strftime("%Y-%m")
        if key == month_key:
            total += int(credits or 0)
    return total


def oxylabs_credit_status(db: Session, settings: Settings) -> dict:
    """
    Remaining Oxylabs results for the soft monthly budget.

    Oxylabs /v2/stats/limits is often unavailable on trial accounts (404).
    We use /v2/stats usage when possible, else local hunt run totals, against
    OXYLABS_MONTHLY_CREDIT_BUDGET (default 1000).
    """
    month_key = current_month_key()
    budget = max(0, int(settings.oxylabs_monthly_credit_budget))
    source = "budget"
    used: int | None = None

    if oxylabs_configured(settings):
        used = OxylabsClient(settings).fetch_month_results_used(month_key=month_key)
        if used is not None:
            source = "oxylabs_stats"

    if used is None:
        used = local_hunt_credits_used(db, month_key=month_key)
        source = "local_hunts"

    remaining = max(0, budget - used)
    return {
        "month_key": month_key,
        "monthly_budget": budget,
        "credits_used": used,
        "credits_remaining": remaining,
        "source": source,
        "configured": oxylabs_configured(settings),
    }
