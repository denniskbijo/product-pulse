from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import Category, ProductSnapshot, SyncRun

SEED_CATEGORIES = [
    {
        "slug": "watchlist",
        "name": "Watchlist",
        "bestsellers_url": "https://www.amazon.co.uk/",
    },
    {
        "slug": "winter-hunt",
        "name": "Winter Hunt",
        "bestsellers_url": "https://www.amazon.co.uk/",
    },
    {
        "slug": "home-kitchen",
        "name": "Home & Kitchen",
        "bestsellers_url": "https://www.amazon.co.uk/gp/bestsellers/kitchen",
    },
    {
        "slug": "electronics",
        "name": "Electronics & Photo",
        "bestsellers_url": "https://www.amazon.co.uk/gp/bestsellers/electronics",
    },
    {
        "slug": "beauty",
        "name": "Beauty",
        "bestsellers_url": "https://www.amazon.co.uk/gp/bestsellers/beauty",
    },
]


def _migrate_featured_to_watchlist(db: Session) -> None:
    """Rename or merge legacy Featured into Watchlist without slug collisions."""
    legacy = db.scalar(select(Category).where(Category.slug == "featured"))
    if legacy is None:
        return

    watchlist = db.scalar(select(Category).where(Category.slug == "watchlist"))
    if watchlist is None:
        legacy.slug = "watchlist"
        legacy.name = "Watchlist"
        db.flush()
        return

    # Both rows exist (partial prior seed): move children, drop legacy.
    # Prefer existing watchlist rows when (asin, week) already present.
    watch_keys = {
        (row.asin, row.week_start)
        for row in db.scalars(
            select(ProductSnapshot).where(ProductSnapshot.category_id == watchlist.id)
        ).all()
    }
    for snap in list(
        db.scalars(
            select(ProductSnapshot).where(ProductSnapshot.category_id == legacy.id)
        ).all()
    ):
        key = (snap.asin, snap.week_start)
        if key in watch_keys:
            db.delete(snap)
        else:
            snap.category_id = watchlist.id
            watch_keys.add(key)

    db.execute(
        update(SyncRun)
        .where(SyncRun.category_id == legacy.id)
        .values(category_id=watchlist.id)
    )
    db.delete(legacy)
    watchlist.name = "Watchlist"
    watchlist.bestsellers_url = "https://www.amazon.co.uk/"
    db.flush()


def seed_categories(db: Session) -> None:
    _migrate_featured_to_watchlist(db)

    for item in SEED_CATEGORIES:
        existing = db.scalar(select(Category).where(Category.slug == item["slug"]))
        if existing:
            existing.name = item["name"]
            existing.bestsellers_url = item["bestsellers_url"]
        else:
            db.add(Category(**item))
    db.commit()
