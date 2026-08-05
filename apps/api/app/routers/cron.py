"""Secured cron endpoints for Vercel Cron / external schedulers."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.daily_prices import run_daily_price_scrape
from app.db import get_db

router = APIRouter(prefix="/cron", tags=["cron"])


def _authorized(authorization: str | None, cron_secret: str) -> bool:
    if not cron_secret:
        return False
    if not authorization:
        return False
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return False
    return hmac.compare_digest(token, cron_secret)


def require_cron_secret(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    if not settings.cron_secret.strip():
        raise HTTPException(
            status_code=503,
            detail="CRON_SECRET is not configured on this deployment.",
        )
    if not _authorized(authorization, settings.cron_secret.strip()):
        raise HTTPException(status_code=401, detail="Invalid cron credentials")


class DailyPricesCronOut(BaseModel):
    status: str
    observed_on: str
    requested: int = 0
    succeeded: int = 0
    failed: int = 0
    asins: list[str] = Field(default_factory=list)
    message: str | None = None


@router.get("/daily-prices", response_model=DailyPricesCronOut)
@router.post("/daily-prices", response_model=DailyPricesCronOut)
def cron_daily_prices(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    _: None = Depends(require_cron_secret),
) -> DailyPricesCronOut:
    """Scrape Amazon mobile prices for tracked ASINs (no Easyparser credits)."""
    summary = run_daily_price_scrape(db, settings=settings)
    if summary.requested == 0:
        return DailyPricesCronOut(
            status="empty",
            observed_on=summary.observed_on.isoformat(),
            message="No weekly snapshot ASINs found. Run a category sync first.",
        )
    status = "success" if summary.succeeded > 0 else "failed"
    return DailyPricesCronOut(
        status=status,
        observed_on=summary.observed_on.isoformat(),
        requested=summary.requested,
        succeeded=summary.succeeded,
        failed=summary.failed,
        asins=summary.asins,
    )
