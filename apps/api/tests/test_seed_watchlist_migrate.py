from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Category, Product, ProductSnapshot
from app.seed import seed_categories
from datetime import date


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_seed_renames_featured_to_watchlist():
    db = _session()
    db.add(
        Category(
            slug="featured",
            name="Featured",
            bestsellers_url="https://www.amazon.co.uk/",
        )
    )
    db.commit()

    seed_categories(db)

    cats = list(db.scalars(select(Category)).all())
    slugs = {c.slug for c in cats}
    assert "featured" not in slugs
    assert "watchlist" in slugs
    watch = next(c for c in cats if c.slug == "watchlist")
    assert watch.name == "Watchlist"


def test_seed_merges_when_both_featured_and_watchlist_exist():
    db = _session()
    featured = Category(
        slug="featured",
        name="Featured",
        bestsellers_url="https://www.amazon.co.uk/",
    )
    watchlist = Category(
        slug="watchlist",
        name="Watchlist",
        bestsellers_url="https://www.amazon.co.uk/",
    )
    db.add_all([featured, watchlist])
    db.flush()
    db.add(Product(asin="B0MERGE0001", title="Merged"))
    db.add(
        ProductSnapshot(
            category_id=featured.id,
            asin="B0MERGE0001",
            week_start=date(2026, 8, 3),
            rank=1,
            price=9.0,
            currency="GBP",
        )
    )
    db.commit()

    seed_categories(db)

    cats = list(db.scalars(select(Category)).all())
    assert {c.slug for c in cats} == {
        "watchlist",
        "winter-hunt",
        "home-kitchen",
        "electronics",
        "beauty",
    }
    snaps = list(db.scalars(select(ProductSnapshot)).all())
    assert len(snaps) == 1
    assert snaps[0].category_id == next(c.id for c in cats if c.slug == "watchlist")


def test_seed_is_idempotent_after_rename():
    db = _session()
    db.add(
        Category(
            slug="featured",
            name="Featured",
            bestsellers_url="https://www.amazon.co.uk/",
        )
    )
    db.commit()
    seed_categories(db)
    seed_categories(db)
    assert (
        len(list(db.scalars(select(Category).where(Category.slug == "watchlist")))) == 1
    )
