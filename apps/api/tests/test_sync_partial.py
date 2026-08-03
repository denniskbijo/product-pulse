from datetime import date
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.math_estimates import week_start_for
from app.models import Category, Product, ProductSnapshot
from app.providers.discovery.bestsellers_html import BestsellerEntry
from app.providers.enrichment.easyparser import EnrichedProduct
from app.sync import run_category_sync


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _settings():
    settings = MagicMock()
    settings.easyparser_api_key = "test-key"
    settings.sync_top_n = 10
    settings.monthly_credit_budget = 100
    return settings


def _enriched(asin: str, title: str, price: float) -> EnrichedProduct:
    return EnrichedProduct(
        asin=asin,
        title=title,
        image_url=None,
        brand=None,
        product_url=f"https://www.amazon.co.uk/dp/{asin}",
        price=price,
        currency="GBP",
        bsr=100,
        rating=4.0,
        review_count=10,
        monthly_sold=43,
        raw={},
        credit_used=1,
        credits_remaining=99,
    )


def test_partial_sync_keeps_existing_week_products():
    db = _session()
    settings = _settings()
    cat = Category(
        slug="home-kitchen",
        name="Home & Kitchen",
        bestsellers_url="https://www.amazon.co.uk/gp/bestsellers/kitchen",
    )
    db.add(cat)
    db.flush()
    week = week_start_for(date.today())
    db.add(Product(asin="B0EXISTING1", title="Existing"))
    db.add(
        ProductSnapshot(
            category_id=cat.id,
            asin="B0EXISTING1",
            week_start=week,
            rank=1,
            price=9.99,
        )
    )
    db.commit()

    with (
        patch(
            "app.sync.discover_bestsellers",
            return_value=([BestsellerEntry(rank=1, asin="B0NEWASIN01")], 0, "amazon_html"),
        ),
        patch("app.sync.EasyparserClient") as client_cls,
    ):
        client = client_cls.return_value
        client.ensure_budget.return_value = None
        client.get_detail.return_value = _enriched("B0NEWASIN01", "New One", 12.0)
        client.last_credits_remaining = 99
        run_category_sync(db, cat, settings=settings, top_n=1)

    asins = set(
        db.scalars(
            select(ProductSnapshot.asin).where(
                ProductSnapshot.category_id == cat.id,
                ProductSnapshot.week_start == week,
            )
        ).all()
    )
    assert asins == {"B0EXISTING1", "B0NEWASIN01"}


def test_full_top_n_sync_keeps_existing_week_products():
    db = _session()
    settings = _settings()
    cat = Category(
        slug="home-kitchen",
        name="Home & Kitchen",
        bestsellers_url="https://www.amazon.co.uk/gp/bestsellers/kitchen",
    )
    db.add(cat)
    db.flush()
    week = week_start_for(date.today())
    db.add(Product(asin="B0EXISTING1", title="Existing"))
    db.add(
        ProductSnapshot(
            category_id=cat.id,
            asin="B0EXISTING1",
            week_start=week,
            rank=3,
            price=9.99,
        )
    )
    db.commit()

    entries = [
        BestsellerEntry(rank=1, asin="B0NEWASIN01"),
        BestsellerEntry(rank=2, asin="B0NEWASIN02"),
    ]
    details = {
        "B0NEWASIN01": _enriched("B0NEWASIN01", "New One", 12.0),
        "B0NEWASIN02": _enriched("B0NEWASIN02", "New Two", 15.0),
    }

    with (
        patch("app.sync.discover_bestsellers", return_value=(entries, 0, "amazon_html")),
        patch("app.sync.EasyparserClient") as client_cls,
    ):
        client = client_cls.return_value
        client.ensure_budget.return_value = None
        client.get_detail.side_effect = lambda asin: details[asin]
        client.last_credits_remaining = 99
        run_category_sync(db, cat, settings=settings, top_n=10)

    asins = set(
        db.scalars(
            select(ProductSnapshot.asin).where(
                ProductSnapshot.category_id == cat.id,
                ProductSnapshot.week_start == week,
            )
        ).all()
    )
    assert asins == {"B0EXISTING1", "B0NEWASIN01", "B0NEWASIN02"}
    existing = db.scalar(
        select(ProductSnapshot).where(
            ProductSnapshot.asin == "B0EXISTING1",
            ProductSnapshot.week_start == week,
        )
    )
    assert existing is not None
    assert existing.rank == 3
    assert existing.price == 9.99
