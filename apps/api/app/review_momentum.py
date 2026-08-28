"""Review-count velocity as a lagged demand signal (not unit sales)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyReviewPoint, Product


def classify_review_momentum(adds: list[int]) -> str:
    """
    Label recent review velocity.

    adds: chronological reviews_added values (oldest first), typically last 7 days.
    """
    if not adds:
        return "unknown"
    last7 = adds[-7:]
    total = sum(last7)
    if total == 0:
        return "quiet"
    if len(last7) >= 4:
        recent = sum(last7[-3:]) / 3
        older = sum(last7[:-3]) / len(last7[:-3])
        if older > 0 and recent >= older * 1.5:
            return "rising"
        if recent == 0 and older > 0:
            return "quiet"
    return "steady"


def previous_review_count(
    db: Session, *, asin: str, before: date
) -> int | None:
    row = db.scalar(
        select(DailyReviewPoint)
        .where(
            DailyReviewPoint.asin == asin,
            DailyReviewPoint.observed_on < before,
            DailyReviewPoint.status == "success",
            DailyReviewPoint.review_count.is_not(None),
        )
        .order_by(DailyReviewPoint.observed_on.desc())
        .limit(1)
    )
    return row.review_count if row is not None else None


def upsert_daily_review_point(
    db: Session,
    *,
    asin: str,
    review_count: int | None,
    rating: float | None = None,
    observed_on: date | None = None,
    source: str = "amazon_mobile",
    status: str = "success",
    error_message: str | None = None,
) -> DailyReviewPoint:
    observed_on = observed_on or date.today()
    if db.get(Product, asin) is None:
        db.add(Product(asin=asin))
        db.flush()

    existing = db.scalar(
        select(DailyReviewPoint).where(
            DailyReviewPoint.asin == asin,
            DailyReviewPoint.observed_on == observed_on,
        )
    )
    if existing is None:
        existing = DailyReviewPoint(asin=asin, observed_on=observed_on)
        db.add(existing)

    reviews_added: int | None = None
    if status == "success" and review_count is not None:
        prev = previous_review_count(db, asin=asin, before=observed_on)
        if prev is not None:
            reviews_added = max(0, review_count - prev)

    existing.source = source
    existing.status = status
    existing.review_count = review_count
    existing.reviews_added = reviews_added
    existing.rating = rating
    existing.error_message = error_message
    return existing


def review_signal_for_asin(
    db: Session, *, asin: str, on_or_before: date | None = None
) -> tuple[int | None, int | None, int | None, str]:
    """Latest count, reviews added that day, 7-day adds, momentum label."""
    on_or_before = on_or_before or date.today()
    rows = list(
        db.scalars(
            select(DailyReviewPoint)
            .where(
                DailyReviewPoint.asin == asin,
                DailyReviewPoint.observed_on <= on_or_before,
                DailyReviewPoint.status == "success",
                DailyReviewPoint.review_count.is_not(None),
            )
            .order_by(DailyReviewPoint.observed_on.desc())
            .limit(8)
        ).all()
    )
    if not rows:
        return None, None, None, "unknown"
    latest = rows[0]
    chronological = list(reversed(rows[:7]))
    if not any(r.reviews_added is not None for r in chronological):
        return latest.review_count, None, None, "unknown"
    adds = [int(r.reviews_added or 0) for r in chronological]
    return (
        latest.review_count,
        latest.reviews_added,
        sum(adds),
        classify_review_momentum(adds),
    )
