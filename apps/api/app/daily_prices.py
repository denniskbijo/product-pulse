"""Daily Amazon mobile price scrape for weekly-tracked ASINs (no Easyparser)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Category, DailyPricePoint, Product, ProductSnapshot
from app.providers.prices.amazon_mobile import fetch_mobile_price
from app.review_momentum import upsert_daily_review_point


@dataclass(frozen=True)
class DailyScrapeSummary:
    observed_on: date
    requested: int
    succeeded: int
    failed: int
    asins: list[str]


def _asins_for_category_latest_week(
    db: Session, *, category_slug: str, max_n: int | None = None
) -> list[str]:
    category_id = db.scalar(
        select(Category.id).where(Category.slug == category_slug)
    )
    if category_id is None:
        return []

    latest_week = db.scalar(
        select(ProductSnapshot.week_start)
        .where(ProductSnapshot.category_id == category_id)
        .order_by(ProductSnapshot.week_start.desc())
        .limit(1)
    )
    if latest_week is None:
        return []

    rows = db.execute(
        select(ProductSnapshot.asin, ProductSnapshot.rank)
        .where(
            ProductSnapshot.category_id == category_id,
            ProductSnapshot.week_start == latest_week,
        )
        .order_by(ProductSnapshot.rank.asc())
    ).all()

    ordered: list[str] = []
    seen: set[str] = set()
    for asin, _rank in rows:
        if asin in seen:
            continue
        seen.add(asin)
        ordered.append(asin)
        if max_n is not None and len(ordered) >= max_n:
            break
    return ordered


def asins_from_latest_weekly_snapshots(db: Session, *, max_n: int) -> list[str]:
    """
    Pick ASINs for the daily price scrape.

    Watchlist products are always first (full latest watchlist week), then other
    categories fill remaining slots up to max_n. This keeps the shared Watchlist
    covered even when seasonal-hunt / bestsellers consume the rank budget.
    """
    watchlist = _asins_for_category_latest_week(db, category_slug="watchlist")
    ordered: list[str] = list(watchlist)
    seen: set[str] = set(watchlist)

    latest_week = db.scalar(
        select(ProductSnapshot.week_start)
        .order_by(ProductSnapshot.week_start.desc())
        .limit(1)
    )
    if latest_week is not None and len(ordered) < max_n:
        rows = db.execute(
            select(
                ProductSnapshot.asin,
                ProductSnapshot.rank,
                ProductSnapshot.category_id,
            )
            .where(ProductSnapshot.week_start == latest_week)
            .order_by(ProductSnapshot.rank.asc(), ProductSnapshot.category_id.asc())
        ).all()
        for asin, _rank, _category_id in rows:
            if asin in seen:
                continue
            seen.add(asin)
            ordered.append(asin)
            if len(ordered) >= max_n:
                break

    # Always cover the whole Watchlist even if it exceeds max_n; otherwise trim.
    if len(watchlist) >= max_n:
        return watchlist
    return ordered[:max_n]


def run_daily_price_scrape(
    db: Session,
    *,
    settings: Settings | None = None,
    observed_on: date | None = None,
    asins: list[str] | None = None,
) -> DailyScrapeSummary:
    settings = settings or get_settings()
    observed_on = observed_on or date.today()
    max_n = max(1, settings.daily_scrape_max)
    delay = max(0.0, settings.daily_scrape_delay_seconds)

    targets = (
        asins
        if asins is not None
        else asins_from_latest_weekly_snapshots(db, max_n=max_n)
    )

    succeeded = 0
    failed = 0
    watchlist_asins = set(_asins_for_category_latest_week(db, category_slug="watchlist"))

    for index, asin in enumerate(targets):
        # Ensure FK target exists even if scrape fails.
        if db.get(Product, asin) is None:
            db.add(Product(asin=asin))
            db.flush()

        result = fetch_mobile_price(asin, host=settings.amazon_marketplace_host)
        existing = db.scalar(
            select(DailyPricePoint).where(
                DailyPricePoint.asin == asin,
                DailyPricePoint.observed_on == observed_on,
            )
        )
        if existing is None:
            existing = DailyPricePoint(asin=asin, observed_on=observed_on)
            db.add(existing)

        existing.source = "amazon_mobile"
        existing.status = result.status
        existing.price = result.price
        existing.currency = result.currency
        existing.error_message = result.error

        if asin in watchlist_asins:
            if result.review_count is not None:
                upsert_daily_review_point(
                    db,
                    asin=asin,
                    review_count=result.review_count,
                    rating=result.rating,
                    observed_on=observed_on,
                    status="success",
                )
            else:
                upsert_daily_review_point(
                    db,
                    asin=asin,
                    review_count=None,
                    rating=None,
                    observed_on=observed_on,
                    status=(
                        result.status
                        if result.status != "success"
                        else "parse_error"
                    ),
                    error_message=result.error or "No review count in mobile HTML",
                )

        if result.status == "success" and result.price is not None:
            succeeded += 1
        else:
            failed += 1

        db.commit()

        if index < len(targets) - 1 and delay > 0:
            time.sleep(delay)

    return DailyScrapeSummary(
        observed_on=observed_on,
        requested=len(targets),
        succeeded=succeeded,
        failed=failed,
        asins=targets,
    )
