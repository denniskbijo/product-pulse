"""Seasonal product hunt — Easyparser SEARCH only (1 credit per run)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings
from app.credits import credit_status, get_or_create_ledger, record_credit_usage
from app.hunt_catalog import (
    HUNT_RUNS_TO_KEEP,
    HUNT_TOP_N,
    get_product_type,
    get_season,
)
from app.models import HuntResult, HuntRun
from app.providers.enrichment.easyparser import CreditBudgetExceeded, EasyparserClient
from app.schemas import (
    HuntResultOut,
    HuntRunDetailOut,
    HuntRunSummaryOut,
)


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
    ledger = get_or_create_ledger(db)
    client = EasyparserClient(settings, credits_used_this_month=ledger.credits_used)

    run = HuntRun(
        season_slug=season.slug,
        product_type_slug=product_type.slug,
        product_type_name=product_type.name,
        search_keyword=product_type.search_keyword,
        top_n=top_n,
        status="running",
        created_by=created_by,
    )
    db.add(run)
    db.flush()

    if not settings.easyparser_api_key.strip():
        run.status = "failed"
        run.error_message = "Product lookup is not configured. Ask an admin to finish setup."
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return get_hunt_run(db, run.id)  # type: ignore[return-value]

    try:
        client.ensure_budget(1)
    except CreditBudgetExceeded as exc:
        run.status = "budget_exceeded"
        run.error_message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return get_hunt_run(db, run.id)  # type: ignore[return-value]

    try:
        hits, credit_used = client.search_catalog(
            keyword=product_type.search_keyword, top_n=top_n
        )
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.error_message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
        return get_hunt_run(db, run.id)  # type: ignore[return-value]

    record_credit_usage(
        db,
        used=credit_used,
        remaining_reported=client.last_credits_remaining,
        settings=settings,
    )

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

    run.status = "success"
    run.credits_used = credit_used
    run.finished_at = datetime.now(timezone.utc)
    _prune_old_runs(db)
    db.commit()
    detail = get_hunt_run(db, run.id)
    assert detail is not None
    # Attach fresh credit snapshot for admin UI.
    detail.credits_remaining_budget = credit_status(db, settings)[
        "credits_remaining_budget"
    ]
    return detail


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
        credits_used=run.credits_used,
        result_count=len(results),
        error_message=run.error_message,
        created_by=run.created_by,
        started_at=run.started_at,
        finished_at=run.finished_at,
        disclaimer=(
            "Current UK demand from Amazon search and “bought past month” badges — "
            "not historical December bestsellers or multi-year winter sales."
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
