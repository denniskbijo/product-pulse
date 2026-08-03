from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings
from app.math_estimates import price_change, week_start_for
from app.models import Category, ProductSnapshot
from app.schemas import CategoryOut, CategoryTopOut, TopProductOut
from app.sync import build_sync_status


def _latest_week_start(db: Session, category_id: int) -> date | None:
    return db.scalar(
        select(ProductSnapshot.week_start)
        .where(ProductSnapshot.category_id == category_id)
        .order_by(ProductSnapshot.week_start.desc())
        .limit(1)
    )


def get_category_top(
    db: Session,
    category: Category,
    settings: Settings,
    *,
    window: str = "7d",
) -> CategoryTopOut:
    week_start = _latest_week_start(db, category.id)
    sync = build_sync_status(db, category.id, settings)

    if week_start is None:
        return CategoryTopOut(
            category=CategoryOut.model_validate(category),
            window=window,
            week_start=None,
            as_of=sync.last_sync_at,
            price_history_ready=False,
            note="No snapshots yet. Trigger a sync to pull this week's top 10.",
            products=[],
            sync=sync,
        )

    previous_week = week_start - timedelta(days=7)
    current_rows = db.scalars(
        select(ProductSnapshot)
        .options(joinedload(ProductSnapshot.product))
        .where(
            ProductSnapshot.category_id == category.id,
            ProductSnapshot.week_start == week_start,
        )
        .order_by(ProductSnapshot.rank.asc(), ProductSnapshot.id.desc())
        .limit(settings.sync_top_n)
    ).all()

    previous_by_asin = {
        row.asin: row
        for row in db.scalars(
            select(ProductSnapshot).where(
                ProductSnapshot.category_id == category.id,
                ProductSnapshot.week_start == previous_week,
            )
        ).all()
    }

    price_history_ready = bool(previous_by_asin)
    products: list[TopProductOut] = []
    for row in current_rows:
        prev = previous_by_asin.get(row.asin)
        delta = price_change(row.price, prev.price if prev else None)
        product = row.product
        products.append(
            TopProductOut(
                rank=row.rank,
                asin=row.asin,
                title=product.title if product else None,
                image_url=product.image_url if product else None,
                brand=product.brand if product else None,
                product_url=product.product_url
                if product and product.product_url
                else f"https://www.amazon.co.uk/dp/{row.asin}",
                price=row.price,
                currency=row.currency or "GBP",
                price_change_absolute=delta.absolute,
                price_change_percent=delta.percent,
                estimated_weekly_units=row.estimated_weekly_units,
                sales_estimate_source=row.sales_estimate_source,
                bsr=row.bsr,
                rating=row.rating,
                review_count=row.review_count,
                monthly_sold=row.monthly_sold,
            )
        )

    note = None
    if not price_history_ready:
        note = (
            "Price change available after the next weekly sync "
            f"(current week start {week_start.isoformat()})."
        )

    return CategoryTopOut(
        category=CategoryOut.model_validate(category),
        window=window,
        week_start=week_start,
        as_of=sync.last_sync_at,
        price_history_ready=price_history_ready,
        note=note,
        products=products,
        sync=sync,
    )


def resolve_category(db: Session, category_id: int | str) -> Category | None:
    if isinstance(category_id, int) or str(category_id).isdigit():
        return db.get(Category, int(category_id))
    return db.scalar(select(Category).where(Category.slug == str(category_id)))


def current_week_start() -> date:
    return week_start_for(date.today())
