from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.daily_prices import asins_from_latest_weekly_snapshots
from app.db import Base
from app.models import Category, Product, ProductSnapshot


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_asins_from_latest_weekly_snapshots_respects_max_and_rank():
    db = _session()
    cat = Category(
        slug="home-kitchen",
        name="Home & Kitchen",
        bestsellers_url="https://www.amazon.co.uk/gp/bestsellers/kitchen",
    )
    db.add(cat)
    db.flush()

    for asin in ("B0AAAAAAA1", "B0AAAAAAA2", "B0AAAAAAA3"):
        db.add(Product(asin=asin))
    db.flush()

    older = date(2026, 7, 27)
    newer = date(2026, 8, 3)
    db.add_all(
        [
            ProductSnapshot(
                category_id=cat.id, asin="B0AAAAAAA1", week_start=older, rank=1, price=1
            ),
            ProductSnapshot(
                category_id=cat.id, asin="B0AAAAAAA2", week_start=newer, rank=2, price=2
            ),
            ProductSnapshot(
                category_id=cat.id, asin="B0AAAAAAA3", week_start=newer, rank=1, price=3
            ),
        ]
    )
    db.commit()

    asins = asins_from_latest_weekly_snapshots(db, max_n=10)
    assert asins == ["B0AAAAAAA3", "B0AAAAAAA2"]

    limited = asins_from_latest_weekly_snapshots(db, max_n=1)
    assert limited == ["B0AAAAAAA3"]
