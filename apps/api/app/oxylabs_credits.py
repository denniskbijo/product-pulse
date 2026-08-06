"""Hardened Oxylabs credit budget — reserve before each hunt request."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import OxylabsCreditLedger
from app.providers.discovery.oxylabs import OxylabsClient, oxylabs_configured


class OxylabsBudgetExceeded(RuntimeError):
    pass


def current_month_key(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    return stamp.strftime("%Y-%m")


def get_or_create_oxylabs_ledger(
    db: Session, month_key: str | None = None
) -> OxylabsCreditLedger:
    month_key = month_key or current_month_key()
    ledger = db.scalar(
        select(OxylabsCreditLedger).where(OxylabsCreditLedger.month_key == month_key)
    )
    if ledger is None:
        ledger = OxylabsCreditLedger(month_key=month_key, credits_used=0)
        db.add(ledger)
        db.commit()
        db.refresh(ledger)
    return ledger


def sync_ledger_with_remote(db: Session, settings: Settings) -> OxylabsCreditLedger:
    """Raise local ledger to at least Oxylabs-reported monthly usage when available."""
    month_key = current_month_key()
    ledger = get_or_create_oxylabs_ledger(db, month_key)
    if not oxylabs_configured(settings):
        return ledger
    remote = OxylabsClient(settings).fetch_month_results_used(month_key=month_key)
    if remote is not None and remote > ledger.credits_used:
        ledger.credits_used = remote
        db.commit()
        db.refresh(ledger)
    return ledger


def reserve_oxylabs_credit(
    db: Session,
    settings: Settings,
    *,
    amount: int = 1,
) -> OxylabsCreditLedger:
    """
    Atomically reserve Oxylabs results before making an API call.
    Reserved credits are not refunded on failure (conservative billing).
    """
    if amount < 1:
        raise ValueError("amount must be >= 1")
    budget = max(0, int(settings.oxylabs_monthly_credit_budget))
    month_key = current_month_key()
    sync_ledger_with_remote(db, settings)
    get_or_create_oxylabs_ledger(db, month_key)

    # Atomic conditional increment — prevents concurrent hunts racing past budget.
    result = db.execute(
        update(OxylabsCreditLedger)
        .where(
            OxylabsCreditLedger.month_key == month_key,
            OxylabsCreditLedger.credits_used + amount <= budget,
        )
        .values(credits_used=OxylabsCreditLedger.credits_used + amount)
    )
    if result.rowcount != 1:
        db.rollback()
        ledger = get_or_create_oxylabs_ledger(db, month_key)
        raise OxylabsBudgetExceeded(
            f"Oxylabs monthly budget exhausted "
            f"({ledger.credits_used}/{budget} used)."
        )
    db.commit()
    return get_or_create_oxylabs_ledger(db, month_key)


def oxylabs_credit_status(db: Session, settings: Settings) -> dict:
    """Remaining Oxylabs results against the configured monthly budget."""
    month_key = current_month_key()
    budget = max(0, int(settings.oxylabs_monthly_credit_budget))
    ledger = sync_ledger_with_remote(db, settings)
    used = int(ledger.credits_used)
    remaining = max(0, budget - used)
    source = "ledger"
    if oxylabs_configured(settings):
        # Indicate we may have synced from Oxylabs stats into the ledger.
        source = "ledger+oxylabs_stats"
    return {
        "month_key": month_key,
        "monthly_budget": budget,
        "credits_used": used,
        "credits_remaining": remaining,
        "source": source,
        "configured": oxylabs_configured(settings),
    }
