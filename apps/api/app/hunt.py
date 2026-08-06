"""Seasonal product hunt — Oxylabs only; auto-saves winners to Winter Hunt category."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings
from app.hunt_catalog import (
    HUNT_RUNS_TO_KEEP,
    HUNT_TOP_N,
    get_product_type,
    get_season,
)
from app.math_estimates import estimate_weekly_units, week_start_for
from app.models import HuntResult, HuntRun, Product, ProductSnapshot
from app.providers.discovery.oxylabs import OxylabsClient, oxylabs_configured
from app.schemas import (
    HuntPromoteOut,
    HuntResultOut,
    HuntRunDetailOut,
    HuntRunSummaryOut,
    WatchlistProductAddOut,
)
from app.services import resolve_category

HUNT_CATEGORY_SLUG = "winter-hunt"
# One Oxylabs realtime query per hunt (amazon_search or amazon_bestsellers).
OXYLABS_REQUESTS_PER_HUNT = 1


def _sort_hits_key(monthly_sold: int | None, search_position: int) -> tuple:
    # Higher monthly_sold first; nulls last; then better search position.
    if monthly_sold is None:
        return (1, 0, search_position)
    return (0, -monthly_sold, search_position)


def _prune_old_runs(db: Session) -> None:
    ids = list(
        db.scalars(
            select(HuntRun.id).order_by(HuntRun.started_at.desc(), HuntRun.id.desc())
        ).all()
    )
    if len(ids) <= HUNT_RUNS_TO_KEEP:
        return
    stale = ids[HUNT_RUNS_TO_KEEP :]
    db.execute(delete(HuntResult).where(HuntResult.run_id.in_(stale)))
    db.execute(delete(HuntRun).where(HuntRun.id.in_(stale)))


def run_hunt(
    db: Session,
    *,
    season_slug: str,
    product_type_slug: str,
    settings: Settings,
    created_by: str | None,
) -> HuntRunDetailOut:
    season = get_season(season_slug)
    if season is None:
        raise LookupError(f"Unknown season: {season_slug}")
    product_type = get_product_type(season_slug, product_type_slug)
    if product_type is None:
        raise LookupError(f"Unknown product type: {product_type_slug}")

    top_n = min(max(1, settings.hunt_top_n), HUNT_TOP_N)

    run = HuntRun(
        season_slug=season.slug,
        product_type_slug=product_type.slug,
        product_type_name=product_type.name,
        search_keyword=product_type.search_keyword,
        top_n=top_n,
        status="running",
        provider="oxylabs",
        created_by=created_by,
    )
    db.add(run)
    db.flush()

    if not oxylabs_configured(settings):
        run.status = "failed"
        run.error_message = (
            "Seasonal Hunt requires Oxylabs. Set OXYLABS_USERNAME and "
            "OXYLABS_PASSWORD (no Easyparser fallback)."
        )
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return get_hunt_run(db, run.id)  # type: ignore[return-value]

    client = OxylabsClient(settings)
    try:
        hits, requests_used, source = client.hunt_catalog(
            keyword=product_type.search_keyword,
            top_n=top_n,
            browse_node=product_type.bestsellers_browse_node or None,
        )
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return get_hunt_run(db, run.id)  # type: ignore[return-value]

    _persist_hits(db, run=run, hits=hits)
    run.status = "success"
    run.credits_used = requests_used
    run.provider = f"oxylabs:{source}"
    run.finished_at = datetime.now(timezone.utc)
    _prune_old_runs(db)
    db.commit()

    # Auto-publish into the Winter Hunt category for all signed-in users.
    promote: HuntPromoteOut | None = None
    try:
        promote = promote_hunt_run_to_category(
            db,
            run_id=run.id,
            category_slug=HUNT_CATEGORY_SLUG,
        )
    except Exception:  # noqa: BLE001
        # Hunt itself succeeded; category publish is best-effort.
        promote = None

    detail = get_hunt_run(db, run.id)
    assert detail is not None
    if promote is not None:
        detail.category_slug = promote.category_slug
        detail.category_saved = True
        detail.category_message = promote.message
    return detail


def promote_hunt_run_to_category(
    db: Session,
    *,
    run_id: int,
    category_slug: str = HUNT_CATEGORY_SLUG,
) -> HuntPromoteOut:
    """
    Copy a successful hunt's candidates into a category (default: Winter Hunt).
    Uses hunt SEARCH fields only — no Easyparser DETAIL credits.
    """
    run = db.scalars(
        select(HuntRun)
        .options(joinedload(HuntRun.results))
        .where(HuntRun.id == run_id)
    ).unique().first()
    if run is None:
        raise LookupError("Hunt run not found")
    if run.status != "success":
        raise ValueError(f"Hunt run is not successful (status={run.status})")
    if not run.results:
        raise ValueError("Hunt run has no results to save")

    category = resolve_category(db, category_slug)
    if category is None:
        raise LookupError(f"Category not found: {category_slug}")

    week_start = week_start_for(date.today())
    ordered = sorted(
        run.results,
        key=lambda r: _sort_hits_key(r.monthly_sold, r.search_position),
    )

    added = 0
    updated = 0
    asins: list[str] = []

    for index, hit in enumerate(ordered, start=1):
        product = db.get(Product, hit.asin)
        if product is None:
            product = Product(asin=hit.asin)
            db.add(product)

        product.title = hit.title or product.title
        product.image_url = hit.image_url or product.image_url
        product.brand = hit.brand or product.brand
        product.product_url = hit.product_url or product.product_url

        sales = estimate_weekly_units(hit.monthly_sold, None)
        existing = db.scalar(
            select(ProductSnapshot).where(
                ProductSnapshot.category_id == category.id,
                ProductSnapshot.asin == hit.asin,
                ProductSnapshot.week_start == week_start,
            )
        )
        if existing is None:
            existing = ProductSnapshot(
                category_id=category.id,
                asin=hit.asin,
                week_start=week_start,
                rank=index,
            )
            db.add(existing)
            added += 1
        else:
            existing.rank = index
            updated += 1

        existing.price = hit.price
        existing.currency = hit.currency or "GBP"
        existing.rating = hit.rating
        existing.review_count = hit.review_count
        existing.monthly_sold = hit.monthly_sold
        existing.estimated_weekly_units = sales.weekly_units
        existing.sales_estimate_source = sales.source
        existing.raw_json = {
            "source": "hunt",
            "hunt_run_id": run.id,
            "provider": run.provider,
            "search_keyword": run.search_keyword,
            "product_type_slug": run.product_type_slug,
            "search_position": hit.search_position,
        }
        asins.append(hit.asin)

    db.commit()
    return HuntPromoteOut(
        status="success",
        message=(
            f"Saved {len(asins)} hunt product(s) to {category.name} "
            f"({added} new, {updated} updated)."
        ),
        category_slug=category.slug,
        category_name=category.name,
        week_start=week_start,
        products_added=added,
        products_updated=updated,
        asins=asins,
    )


def add_hunt_result_to_watchlist(
    db: Session,
    *,
    run_id: int,
    asin: str,
) -> WatchlistProductAddOut:
    """
    Add a hunt candidate to Watchlist using hunt fields already fetched.
    No Easyparser DETAIL and no extra Oxylabs request.
    """
    asin = asin.strip().upper()
    run = db.scalars(
        select(HuntRun)
        .options(joinedload(HuntRun.results))
        .where(HuntRun.id == run_id)
    ).unique().first()
    if run is None:
        raise LookupError("Hunt run not found")
    if run.status != "success":
        raise ValueError("Only successful hunt results can be added to Watchlist")

    hit = next((r for r in run.results if r.asin.upper() == asin), None)
    if hit is None:
        raise LookupError(f"ASIN {asin} not found in this hunt run")

    category = resolve_category(db, "watchlist")
    if category is None:
        raise LookupError("Watchlist category not found")

    week_start = week_start_for(date.today())
    product = db.get(Product, asin)
    if product is None:
        product = Product(asin=asin)
        db.add(product)

    product.title = hit.title or product.title
    product.image_url = hit.image_url or product.image_url
    product.brand = hit.brand or product.brand
    product.product_url = hit.product_url or product.product_url

    sales = estimate_weekly_units(hit.monthly_sold, None)
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
    existing.price = hit.price
    existing.currency = hit.currency or "GBP"
    existing.rating = hit.rating
    existing.review_count = hit.review_count
    existing.monthly_sold = hit.monthly_sold
    existing.estimated_weekly_units = sales.weekly_units
    existing.sales_estimate_source = sales.source
    existing.raw_json = {
        "source": "hunt_watchlist",
        "hunt_run_id": run.id,
        "provider": run.provider,
        "search_keyword": run.search_keyword,
    }
    db.commit()

    title = hit.title or product.title
    return WatchlistProductAddOut(
        status="success",
        message=(
            f"Added {title or asin} to Watchlist from hunt (rank {rank}, "
            "0 extra credits)."
        ),
        asin=asin,
        title=title,
        rank=rank,
        credits_used=0,
        credits_remaining_budget=None,
        week_start=week_start,
    )


def _persist_hits(db: Session, *, run: HuntRun, hits) -> None:
    ordered = sorted(
        hits,
        key=lambda h: _sort_hits_key(h.monthly_sold, h.position),
    )
    for hit in ordered:
        db.add(
            HuntResult(
                run_id=run.id,
                search_position=hit.position,
                asin=hit.asin,
                title=hit.title,
                image_url=hit.image_url,
                brand=hit.brand,
                product_url=hit.product_url
                or f"https://www.amazon.co.uk/dp/{hit.asin}",
                price=hit.price,
                currency=hit.currency,
                rating=hit.rating,
                review_count=hit.review_count,
                monthly_sold=hit.monthly_sold,
            )
        )


def list_hunt_runs(db: Session, *, limit: int = 20) -> list[HuntRunSummaryOut]:
    rows = db.scalars(
        select(HuntRun)
        .options(joinedload(HuntRun.results))
        .order_by(HuntRun.started_at.desc(), HuntRun.id.desc())
        .limit(limit)
    ).unique().all()
    return [
        HuntRunSummaryOut(
            id=row.id,
            season_slug=row.season_slug,
            product_type_slug=row.product_type_slug,
            product_type_name=row.product_type_name,
            search_keyword=row.search_keyword,
            top_n=row.top_n,
            status=row.status,
            provider=row.provider,
            credits_used=row.credits_used,
            result_count=len(row.results),
            error_message=row.error_message,
            created_by=row.created_by,
            started_at=row.started_at,
            finished_at=row.finished_at,
        )
        for row in rows
    ]


def get_hunt_run(db: Session, run_id: int) -> HuntRunDetailOut | None:
    run = db.scalars(
        select(HuntRun)
        .options(joinedload(HuntRun.results))
        .where(HuntRun.id == run_id)
    ).unique().first()
    if run is None:
        return None

    results = sorted(
        run.results,
        key=lambda r: _sort_hits_key(r.monthly_sold, r.search_position),
    )
    return HuntRunDetailOut(
        id=run.id,
        season_slug=run.season_slug,
        product_type_slug=run.product_type_slug,
        product_type_name=run.product_type_name,
        search_keyword=run.search_keyword,
        top_n=run.top_n,
        status=run.status,
        provider=run.provider or "oxylabs",
        credits_used=run.credits_used,
        result_count=len(results),
        error_message=run.error_message,
        created_by=run.created_by,
        started_at=run.started_at,
        finished_at=run.finished_at,
        disclaimer=(
            "Current UK demand from Oxylabs Amazon search/bestsellers — "
            "not historical December archives or multi-year winter sales."
        ),
        results=[
            HuntResultOut(
                search_position=r.search_position,
                asin=r.asin,
                title=r.title,
                image_url=r.image_url,
                brand=r.brand,
                product_url=r.product_url,
                price=r.price,
                currency=r.currency,
                rating=r.rating,
                review_count=r.review_count,
                monthly_sold=r.monthly_sold,
            )
            for r in results
        ],
    )
