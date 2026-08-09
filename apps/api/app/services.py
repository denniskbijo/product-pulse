from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.asin import parse_asin_from_input
from app.config import Settings
from app.credits import credit_status, get_or_create_ledger, record_credit_usage
from app.listing_price import resolve_uk_listing_price, upsert_daily_price_point
from app.math_estimates import estimate_weekly_units, price_change, week_start_for
from app.models import Category, DailyPricePoint, Product, ProductSnapshot
from app.providers.enrichment.easyparser import CreditBudgetExceeded, EasyparserClient
from app.schemas import (
    CategoryOut,
    CategoryTopOut,
    WatchlistProductAddOut,
    PriceHistoryPointOut,
    ProductCategorySightingOut,
    ProductDetailOut,
    ProductNotesOut,
    ProductRemoveOut,
    TopProductOut,
)
from app.sync import build_sync_status


def _latest_week_start(db: Session, category_id: int) -> date | None:
    return db.scalar(
        select(ProductSnapshot.week_start)
        .where(ProductSnapshot.category_id == category_id)
        .order_by(ProductSnapshot.week_start.desc())
        .limit(1)
    )


def _daily_prices_by_asin(
    db: Session,
    asins: list[str],
    *,
    on_or_before: date,
) -> dict[str, DailyPricePoint]:
    """Latest successful daily price for each ASIN on/before on_or_before."""
    if not asins:
        return {}
    rows = db.scalars(
        select(DailyPricePoint)
        .where(
            DailyPricePoint.asin.in_(asins),
            DailyPricePoint.observed_on <= on_or_before,
            DailyPricePoint.status == "success",
            DailyPricePoint.price.is_not(None),
        )
        .order_by(DailyPricePoint.asin.asc(), DailyPricePoint.observed_on.desc())
    ).all()
    latest: dict[str, DailyPricePoint] = {}
    for row in rows:
        if row.asin not in latest:
            latest[row.asin] = row
    return latest


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

    asins = [row.asin for row in current_rows]
    today = date.today()
    week_ago = today - timedelta(days=7)
    daily_now = _daily_prices_by_asin(db, asins, on_or_before=today)
    daily_prev = _daily_prices_by_asin(db, asins, on_or_before=week_ago)

    price_history_ready = False
    products: list[TopProductOut] = []
    for row in current_rows:
        product = row.product
        now_daily = daily_now.get(row.asin)
        prev_daily = daily_prev.get(row.asin)

        display_price = now_daily.price if now_daily else row.price
        display_currency = (
            (now_daily.currency if now_daily and now_daily.currency else None)
            or row.currency
            or "GBP"
        )

        # Prefer true ~7-day daily history; fall back to week-vs-week snapshots.
        if (
            now_daily
            and prev_daily
            and now_daily.observed_on != prev_daily.observed_on
        ):
            delta = price_change(now_daily.price, prev_daily.price)
            price_history_ready = True
        else:
            prev = previous_by_asin.get(row.asin)
            delta = price_change(row.price, prev.price if prev else None)
            if prev is not None:
                price_history_ready = True

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
                notes=product.notes if product else None,
                price=display_price,
                currency=display_currency,
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
            "7-day price change appears after a few days of price checks "
            "(or after a second weekly update)."
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


def add_product_to_watchlist(
    db: Session,
    *,
    raw_input: str,
    settings: Settings,
) -> WatchlistProductAddOut:
    asin = parse_asin_from_input(raw_input)
    category = resolve_category(db, "watchlist")
    if category is None:
        raise LookupError("Watchlist category not found")

    week_start = week_start_for(date.today())
    ledger = get_or_create_ledger(db)
    client = EasyparserClient(settings, credits_used_this_month=ledger.credits_used)
    credits = credit_status(db, settings)

    if not settings.easyparser_api_key.strip():
        return WatchlistProductAddOut(
            status="failed",
            message=(
                "Product lookup is not configured. Ask an admin to finish setup."
            ),
            asin=asin,
            week_start=week_start,
            credits_remaining_budget=credits["credits_remaining_budget"],
        )

    try:
        client.ensure_budget(1)
    except CreditBudgetExceeded as exc:
        return WatchlistProductAddOut(
            status="budget_exceeded",
            message=str(exc),
            asin=asin,
            week_start=week_start,
            credits_remaining_budget=credits["credits_remaining_budget"],
        )

    try:
        enriched = client.get_detail(asin)
    except Exception as exc:  # noqa: BLE001
        credits = credit_status(db, settings)
        return WatchlistProductAddOut(
            status="failed",
            message=str(exc),
            asin=asin,
            week_start=week_start,
            credits_remaining_budget=credits["credits_remaining_budget"],
        )

    record_credit_usage(
        db,
        used=enriched.credit_used,
        remaining_reported=client.last_credits_remaining,
        settings=settings,
    )

    product = db.get(Product, asin)
    if product is None:
        product = Product(asin=asin)
        db.add(product)

    product.title = enriched.title or product.title
    product.image_url = enriched.image_url or product.image_url
    product.brand = enriched.brand or product.brand
    product.product_url = enriched.product_url or product.product_url

    sales = estimate_weekly_units(enriched.monthly_sold, enriched.bsr)

    existing = db.scalar(
        select(ProductSnapshot).where(
            ProductSnapshot.category_id == category.id,
            ProductSnapshot.asin == asin,
            ProductSnapshot.week_start == week_start,
        )
    )
    if existing is not None:
        rank = existing.rank
    else:
        max_rank = db.scalar(
            select(func.max(ProductSnapshot.rank)).where(
                ProductSnapshot.category_id == category.id,
                ProductSnapshot.week_start == week_start,
            )
        )
        rank = (max_rank or 0) + 1
        existing = ProductSnapshot(
            category_id=category.id,
            asin=asin,
            week_start=week_start,
            rank=rank,
        )
        db.add(existing)

    existing.rank = rank
    price, currency = resolve_uk_listing_price(
        asin,
        fallback_price=enriched.price,
        fallback_currency=enriched.currency,
        settings=settings,
    )
    existing.price = price
    existing.currency = currency
    if price is not None:
        upsert_daily_price_point(
            db, asin=asin, price=price, currency=currency or "GBP"
        )
    existing.bsr = enriched.bsr
    existing.rating = enriched.rating
    existing.review_count = enriched.review_count
    existing.monthly_sold = enriched.monthly_sold
    existing.estimated_weekly_units = sales.weekly_units
    existing.sales_estimate_source = sales.source
    existing.raw_json = enriched.raw
    db.commit()

    credits = credit_status(db, settings)
    title = enriched.title or product.title
    return WatchlistProductAddOut(
        status="success",
        message=f"Added {title or asin} to Watchlist (rank {rank})",
        asin=asin,
        title=title,
        rank=rank,
        credits_used=enriched.credit_used,
        credits_remaining_budget=credits["credits_remaining_budget"],
        week_start=week_start,
    )


def get_product_detail(db: Session, asin: str) -> ProductDetailOut | None:
    """Return stored Easyparser enrichment + recent price history (no provider calls)."""
    asin = asin.strip().upper()
    product = db.get(Product, asin)
    if product is None:
        return None

    latest_snap = db.scalar(
        select(ProductSnapshot)
        .where(ProductSnapshot.asin == asin)
        .order_by(ProductSnapshot.week_start.desc(), ProductSnapshot.id.desc())
        .limit(1)
    )

    sightings = db.execute(
        select(
            Category.slug,
            Category.name,
            ProductSnapshot.rank,
            ProductSnapshot.week_start,
        )
        .join(Category, Category.id == ProductSnapshot.category_id)
        .where(ProductSnapshot.asin == asin)
        .order_by(ProductSnapshot.week_start.desc(), ProductSnapshot.rank.asc())
        .limit(20)
    ).all()
    # Keep one row per category (latest week).
    seen_cats: set[str] = set()
    categories: list[ProductCategorySightingOut] = []
    for slug, name, rank, week_start in sightings:
        if slug in seen_cats:
            continue
        seen_cats.add(slug)
        categories.append(
            ProductCategorySightingOut(
                slug=slug, name=name, rank=rank, week_start=week_start
            )
        )

    today = date.today()
    history_start = today - timedelta(days=30)
    daily_rows = db.scalars(
        select(DailyPricePoint)
        .where(
            DailyPricePoint.asin == asin,
            DailyPricePoint.observed_on >= history_start,
            DailyPricePoint.status == "success",
            DailyPricePoint.price.is_not(None),
        )
        .order_by(DailyPricePoint.observed_on.asc())
    ).all()

    by_day: dict[date, PriceHistoryPointOut] = {
        row.observed_on: PriceHistoryPointOut(
            date=row.observed_on,
            price=float(row.price),  # type: ignore[arg-type]
            currency=row.currency or "GBP",
            source="amazon_mobile",
        )
        for row in daily_rows
    }

    # Fill gaps with weekly snapshot prices (dated as week_start).
    weekly_rows = db.scalars(
        select(ProductSnapshot)
        .where(
            ProductSnapshot.asin == asin,
            ProductSnapshot.week_start >= history_start,
            ProductSnapshot.price.is_not(None),
        )
        .order_by(ProductSnapshot.week_start.asc())
    ).all()
    for row in weekly_rows:
        if row.week_start not in by_day and row.price is not None:
            by_day[row.week_start] = PriceHistoryPointOut(
                date=row.week_start,
                price=float(row.price),
                currency=row.currency or "GBP",
                source="weekly_snapshot",
            )

    price_history = [by_day[d] for d in sorted(by_day)]

    now_daily = _daily_prices_by_asin(db, [asin], on_or_before=today).get(asin)
    prev_daily = _daily_prices_by_asin(
        db, [asin], on_or_before=today - timedelta(days=7)
    ).get(asin)

    display_price = (
        now_daily.price
        if now_daily
        else (latest_snap.price if latest_snap else None)
    )
    display_currency = (
        (now_daily.currency if now_daily and now_daily.currency else None)
        or (latest_snap.currency if latest_snap else None)
        or "GBP"
    )

    if now_daily and prev_daily and now_daily.observed_on != prev_daily.observed_on:
        delta = price_change(now_daily.price, prev_daily.price)
        history_ready = True
    elif latest_snap is not None:
        prev_week = db.scalar(
            select(ProductSnapshot)
            .where(
                ProductSnapshot.asin == asin,
                ProductSnapshot.week_start == latest_snap.week_start - timedelta(days=7),
                ProductSnapshot.price.is_not(None),
            )
            .limit(1)
        )
        delta = price_change(
            latest_snap.price, prev_week.price if prev_week else None
        )
        history_ready = prev_week is not None
    else:
        delta = price_change(None, None)
        history_ready = False

    return ProductDetailOut(
        asin=asin,
        title=product.title,
        image_url=product.image_url,
        brand=product.brand,
        product_url=product.product_url or f"https://www.amazon.co.uk/dp/{asin}",
        notes=product.notes,
        price=display_price,
        currency=display_currency,
        price_change_absolute=delta.absolute,
        price_change_percent=delta.percent,
        price_history_ready=history_ready,
        estimated_weekly_units=latest_snap.estimated_weekly_units if latest_snap else None,
        sales_estimate_source=latest_snap.sales_estimate_source if latest_snap else None,
        bsr=latest_snap.bsr if latest_snap else None,
        rating=latest_snap.rating if latest_snap else None,
        review_count=latest_snap.review_count if latest_snap else None,
        monthly_sold=latest_snap.monthly_sold if latest_snap else None,
        latest_week_start=latest_snap.week_start if latest_snap else None,
        updated_at=product.updated_at,
        categories=categories,
        price_history=price_history,
    )


def update_product_notes(
    db: Session, asin: str, notes: str | None
) -> ProductNotesOut | None:
    asin = asin.strip().upper()
    product = db.get(Product, asin)
    if product is None:
        return None
    cleaned = notes.strip() if notes else ""
    product.notes = cleaned or None
    db.commit()
    db.refresh(product)
    return ProductNotesOut(asin=product.asin, notes=product.notes)


def remove_product_from_category(
    db: Session, category: Category, asin: str
) -> ProductRemoveOut:
    """Remove all weekly snapshots for this ASIN in the given category."""
    asin = asin.strip().upper()
    snapshots = list(
        db.scalars(
            select(ProductSnapshot).where(
                ProductSnapshot.category_id == category.id,
                ProductSnapshot.asin == asin,
            )
        ).all()
    )
    if not snapshots:
        raise LookupError(f"Product {asin} is not in {category.name}")

    for snap in snapshots:
        db.delete(snap)
    db.commit()

    return ProductRemoveOut(
        status="success",
        message=f"Removed {asin} from {category.name}",
        asin=asin,
        category_id=category.id,
        snapshots_removed=len(snapshots),
    )
