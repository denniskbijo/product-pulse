from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Product
from app.review_momentum import (
    classify_review_momentum,
    review_signal_for_asin,
    upsert_daily_review_point,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_classify_review_momentum_labels():
    assert classify_review_momentum([]) == "unknown"
    assert classify_review_momentum([0, 0]) == "quiet"
    assert classify_review_momentum([1, 1, 1, 3, 3, 3]) == "rising"
    assert classify_review_momentum([5, 5, 5, 0, 0, 0]) == "quiet"
    assert classify_review_momentum([2, 2, 3, 2]) == "steady"


def test_upsert_computes_day_over_day_adds():
    db = _session()
    asin = "B0WATCH001"
    day1 = date(2026, 8, 16)
    day2 = date(2026, 8, 17)

    first = upsert_daily_review_point(
        db, asin=asin, review_count=6100, rating=4.1, observed_on=day1
    )
    db.commit()
    assert first.reviews_added is None
    assert db.get(Product, asin) is not None

    second = upsert_daily_review_point(
        db, asin=asin, review_count=6107, rating=4.1, observed_on=day2
    )
    db.commit()
    assert second.reviews_added == 7

    count, added, added_7d, momentum = review_signal_for_asin(
        db, asin=asin, on_or_before=day2
    )
    assert count == 6107
    assert added == 7
    assert added_7d == 7
    assert momentum == "steady"


def test_review_signal_unknown_until_second_day():
    db = _session()
    upsert_daily_review_point(
        db,
        asin="B0WATCH002",
        review_count=100,
        observed_on=date(2026, 8, 16),
    )
    db.commit()
    count, added, added_7d, momentum = review_signal_for_asin(
        db, asin="B0WATCH002", on_or_before=date(2026, 8, 16)
    )
    assert count == 100
    assert added is None
    assert added_7d is None
    assert momentum == "unknown"


def test_review_signal_rising_after_acceleration():
    db = _session()
    asin = "B0WATCH003"
    start = date(2026, 8, 10)
    counts = [100, 101, 102, 103, 106, 110, 115]
    for offset, count in enumerate(counts):
        upsert_daily_review_point(
            db,
            asin=asin,
            review_count=count,
            observed_on=start + timedelta(days=offset),
        )
    db.commit()
    latest, added, added_7d, momentum = review_signal_for_asin(
        db, asin=asin, on_or_before=start + timedelta(days=6)
    )
    assert latest == 115
    assert added == 5
    assert added_7d == 15
    assert momentum == "rising"
