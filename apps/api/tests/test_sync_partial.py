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

    enriched = EnrichedProduct(
        asin="B0NEWASIN01",
        title="New One",
        image_url=None,
        brand=None,
        product_url="https://www.amazon.co.uk/dp/B0NEWASIN01",
        price=12.0,
        currency="GBP",
        bsr=100,
        rating=4.0,
        review_count=10,
        monthly_sold=43,
        raw={},
        credit_used=1,
        credits_remaining=99,
    )

    with (
        patch(
            "app.sync.discover_bestsellers",
            return_value=([BestsellerEntry(rank=1, asin="B0NEWASIN01")], 0, "amazon_html"),
        ),
        patch("app.sync.EasyparserClient") as client_cls,
    ):
        client = client_cls.return_value
        client.ensure_budget.return_value = None
        client.get_detail.return_value = enriched
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
