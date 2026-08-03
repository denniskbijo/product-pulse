from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import CreditLedger


def current_month_key(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    return now.strftime("%Y-%m")


def get_or_create_ledger(db: Session, month_key: str | None = None) -> CreditLedger:
    month_key = month_key or current_month_key()
    ledger = db.scalar(select(CreditLedger).where(CreditLedger.month_key == month_key))
    if ledger is None:
        ledger = CreditLedger(month_key=month_key, credits_used=0)
        db.add(ledger)
        db.commit()
        db.refresh(ledger)
    return ledger


def record_credit_usage(
    db: Session,
    *,
    used: int,
    remaining_reported: int | None,
    settings: Settings,
) -> CreditLedger:
    ledger = get_or_create_ledger(db)
    ledger.credits_used += used
    if remaining_reported is not None:
        ledger.credits_remaining_reported = remaining_reported
    db.commit()
    db.refresh(ledger)
    return ledger


def credit_status(db: Session, settings: Settings) -> dict:
    ledger = get_or_create_ledger(db)
    remaining_budget = max(0, settings.monthly_credit_budget - ledger.credits_used)
    return {
        "monthly_budget": settings.monthly_credit_budget,
        "credits_used": ledger.credits_used,
        "credits_remaining_budget": remaining_budget,
        "credits_remaining_reported": ledger.credits_remaining_reported,
        "month_key": ledger.month_key,
    }
