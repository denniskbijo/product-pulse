from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category

SEED_CATEGORIES = [
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


def seed_categories(db: Session) -> None:
    for item in SEED_CATEGORIES:
        existing = db.scalar(select(Category).where(Category.slug == item["slug"]))
        if existing:
            existing.name = item["name"]
            existing.bestsellers_url = item["bestsellers_url"]
        else:
            db.add(Category(**item))
    db.commit()
