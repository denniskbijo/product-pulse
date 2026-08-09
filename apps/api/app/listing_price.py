"""Resolve the UK listing price used in snapshots / Watchlist adds."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import DailyPricePoint, Product
from app.providers.prices.amazon_mobile import fetch_mobile_price


def resolve_uk_listing_price(
    asin: str,
    *,
    fallback_price: float | None,
    fallback_currency: str | None,
    settings: Settings,
) -> tuple[float | None, str | None]:
    """
    Prefer Amazon UK mobile buybox price.

    Easyparser DETAIL often returns USD amounts (and nested currency) even for
    amazon.co.uk ASINs; those must not be stored as GBP.
    """
    mobile = fetch_mobile_price(asin, host=settings.amazon_marketplace_host)
    if mobile.status == "success" and mobile.price is not None:
        return mobile.price, mobile.currency or "GBP"

    currency = (fallback_currency or "").strip().upper().replace("£", "GBP")
    if fallback_price is not None and currency == "GBP":
        return fallback_price, "GBP"
    # Refuse non-GBP Easyparser prices for the UK marketplace.
    return None, None


def upsert_daily_price_point(
    db: Session,
    *,
    asin: str,
    price: float,
    currency: str | None,
    observed_on: date | None = None,
    source: str = "amazon_mobile",
) -> None:
    """Seed today's daily price so the dashboard prefers the correct UK amount."""
    observed_on = observed_on or date.today()
    if db.get(Product, asin) is None:
        db.add(Product(asin=asin))
        db.flush()

    existing = db.scalar(
        select(DailyPricePoint).where(
            DailyPricePoint.asin == asin,
            DailyPricePoint.observed_on == observed_on,
        )
    )
    if existing is None:
        existing = DailyPricePoint(asin=asin, observed_on=observed_on)
        db.add(existing)

    existing.source = source
    existing.status = "success"
    existing.price = price
    existing.currency = currency or "GBP"
    existing.error_message = None
