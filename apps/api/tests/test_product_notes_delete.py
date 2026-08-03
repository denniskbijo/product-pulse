from datetime import date, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Category, Product, ProductSnapshot
from app.services import (
    get_product_detail,
    remove_product_from_category,
    update_product_notes,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(db):
    cat = Category(
        slug="watchlist",
        name="Watchlist",
        bestsellers_url="https://www.amazon.co.uk/",
    )
    other = Category(
        slug="home-kitchen",
        name="Home & Kitchen",
        bestsellers_url="https://www.amazon.co.uk/gp/bestsellers/kitchen",
    )
    db.add_all([cat, other])
    db.flush()

    asin = "B0NOTEASIN"
    db.add(Product(asin=asin, title="Noteable Product"))
    week = date.today() - timedelta(days=date.today().weekday())
    db.add_all(
        [
            ProductSnapshot(
                category_id=cat.id,
                asin=asin,
                week_start=week,
                rank=1,
                price=10.0,
                currency="GBP",
            ),
            ProductSnapshot(
                category_id=other.id,
                asin=asin,
                week_start=week,
                rank=3,
                price=10.0,
                currency="GBP",
            ),
        ]
    )
    db.commit()
    return cat, other, asin


def test_update_product_notes():
    db = _session()
    _, _, asin = _seed(db)

    result = update_product_notes(db, asin, "  Watch price drop  ")
    assert result is not None
    assert result.notes == "Watch price drop"

    detail = get_product_detail(db, asin)
    assert detail is not None
    assert detail.notes == "Watch price drop"

    cleared = update_product_notes(db, asin, "   ")
    assert cleared is not None
    assert cleared.notes is None


def test_remove_product_from_category_keeps_other_categories():
    db = _session()
    watchlist, home, asin = _seed(db)

    out = remove_product_from_category(db, watchlist, asin)
    assert out.snapshots_removed == 1
    assert out.status == "success"

    remaining = list(
        db.scalars(select(ProductSnapshot).where(ProductSnapshot.asin == asin)).all()
    )
    assert len(remaining) == 1
    assert remaining[0].category_id == home.id
    assert db.get(Product, asin) is not None


def test_remove_missing_product_raises():
    db = _session()
    watchlist, _, _ = _seed(db)
    try:
        remove_product_from_category(db, watchlist, "B0MISSING1")
        raise AssertionError("expected LookupError")
    except LookupError:
        pass
