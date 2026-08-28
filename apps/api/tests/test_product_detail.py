from datetime import date, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Category, DailyPricePoint, DailyReviewPoint, Product, ProductSnapshot
from app.services import get_product_detail


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_get_product_detail_returns_enrichment_and_history():
    db = _session()
    cat = Category(
        slug="watchlist",
        name="Watchlist",
        bestsellers_url="https://www.amazon.co.uk/",
    )
    db.add(cat)
    db.flush()

    asin = "B0TESTASIN"
    db.add(
        Product(
            asin=asin,
            title="Test Kettle",
            brand="Pulse",
            image_url="https://example.com/k.jpg",
            product_url=f"https://www.amazon.co.uk/dp/{asin}",
        )
    )
    today = date.today()
    week = today - timedelta(days=today.weekday())
    db.add(
        ProductSnapshot(
            category_id=cat.id,
            asin=asin,
            week_start=week,
            rank=1,
            price=24.0,
            currency="GBP",
            bsr=1200,
            rating=4.5,
            review_count=100,
            monthly_sold=430,
            estimated_weekly_units=100.0,
            sales_estimate_source="monthly_sold",
        )
    )
    db.add_all(
        [
            DailyPricePoint(
                asin=asin,
                observed_on=today - timedelta(days=7),
                price=22.0,
                currency="GBP",
                status="success",
            ),
            DailyPricePoint(
                asin=asin,
                observed_on=today,
                price=24.0,
                currency="GBP",
                status="success",
            ),
        ]
    )
    db.commit()

    db.add_all(
        [
            DailyReviewPoint(
                asin=asin,
                observed_on=today - timedelta(days=1),
                review_count=100,
                reviews_added=None,
                rating=4.5,
                status="success",
            ),
            DailyReviewPoint(
                asin=asin,
                observed_on=today,
                review_count=104,
                reviews_added=4,
                rating=4.6,
                status="success",
            ),
        ]
    )
    db.commit()

    detail = get_product_detail(db, asin)
    assert detail is not None
    assert detail.title == "Test Kettle"
    assert detail.bsr == 1200
    assert detail.price == 24.0
    assert detail.price_change_absolute == 2.0
    assert detail.price_history_ready is True
    assert len(detail.price_history) >= 2
    assert detail.categories[0].slug == "watchlist"
    assert detail.review_count == 104
    assert detail.reviews_added == 4
    assert detail.reviews_added_7d == 4
    assert detail.review_momentum == "steady"
    assert detail.rating == 4.6
    assert len(detail.review_history) == 2


def test_get_product_detail_missing():
    db = _session()
    assert get_product_detail(db, "B0MISSING1") is None
