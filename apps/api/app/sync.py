from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.credits import credit_status, get_or_create_ledger, record_credit_usage
from app.math_estimates import estimate_weekly_units, week_start_for
from app.models import Category, Product, ProductSnapshot, SyncRun
from app.providers.discovery.bestsellers_html import BestsellerEntry, fetch_bestsellers
from app.providers.enrichment.easyparser import CreditBudgetExceeded, EasyparserClient


def discover_bestsellers(
    category: Category,
    client: EasyparserClient,
    *,
    top_n: int,
) -> tuple[list[BestsellerEntry], int, str]:
    """Try free Amazon HTML, then Easyparser SEARCH keyword (1 credit)."""
    try:
        entries = fetch_bestsellers(category.bestsellers_url, top_n=top_n)
    except Exception:  # noqa: BLE001
        entries = []

    if entries:
        return entries, 0, "amazon_html"

    # Bestsellers URL search is flaky on Easyparser; keyword search is reliable.
    keyword = category.name.split("&")[0].strip() or category.slug.replace("-", " ")
    entries, credit_used = client.search_products(keyword=keyword, top_n=top_n)
    if not entries:
        raise RuntimeError(
            f"Could not discover products via Amazon HTML or Easyparser SEARCH "
            f"(keyword={keyword!r})."
        )
    return entries, credit_used, "easyparser_search"


def run_category_sync(
    db: Session,
    category: Category,
    *,
    settings: Settings | None = None,
    top_n: int | None = None,
) -> SyncRun:
    settings = settings or get_settings()
    top_n = top_n or settings.sync_top_n
    week_start = week_start_for(date.today())

    ledger = get_or_create_ledger(db)
    sync_run = SyncRun(
        category_id=category.id,
        week_start=week_start,
        status="running",
        credits_used=0,
    )
    db.add(sync_run)
    db.commit()
    db.refresh(sync_run)

    client = EasyparserClient(settings, credits_used_this_month=ledger.credits_used)
    credits_this_run = 0
    synced = 0

    try:
        if not settings.easyparser_api_key.strip():
            raise RuntimeError(
                "EASYPARSER_API_KEY is empty. Save it in the project root .env and restart make run."
            )

        client.ensure_budget(1)
        entries, discovery_credits, _source = discover_bestsellers(
            category, client, top_n=top_n
        )
        credits_this_run += discovery_credits
        if discovery_credits:
            record_credit_usage(
                db,
                used=discovery_credits,
                remaining_reported=client.last_credits_remaining,
                settings=settings,
            )

        client.ensure_budget(len(entries))

        # Full top-N sync replaces this week's ranked set. Partial sync (e.g. Sync 1)
        # only upserts discovered ASINs and keeps other products for the week.
        replace_week_set = top_n >= settings.sync_top_n
        if replace_week_set:
            old_rows = db.scalars(
                select(ProductSnapshot).where(
                    ProductSnapshot.category_id == category.id,
                    ProductSnapshot.week_start == week_start,
                )
            ).all()
            for row in old_rows:
                db.delete(row)
            db.flush()

        for entry in entries:
            enriched = client.get_detail(entry.asin)
            credits_this_run += enriched.credit_used

            product = db.get(Product, entry.asin)
            if product is None:
                product = Product(asin=entry.asin)
                db.add(product)

            product.title = enriched.title or product.title
            product.image_url = enriched.image_url or product.image_url
            product.brand = enriched.brand or product.brand
            product.product_url = enriched.product_url or product.product_url

            sales = estimate_weekly_units(enriched.monthly_sold, enriched.bsr)

            existing = db.scalar(
                select(ProductSnapshot).where(
                    ProductSnapshot.category_id == category.id,
                    ProductSnapshot.asin == entry.asin,
                    ProductSnapshot.week_start == week_start,
                )
            )
            if existing is None:
                if replace_week_set:
                    rank = entry.rank
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
                    asin=entry.asin,
                    week_start=week_start,
                    rank=rank,
                )
                db.add(existing)
            elif replace_week_set:
                existing.rank = entry.rank

            existing.price = enriched.price
            existing.currency = enriched.currency
            existing.bsr = enriched.bsr
            existing.rating = enriched.rating
            existing.review_count = enriched.review_count
            existing.monthly_sold = enriched.monthly_sold
            existing.estimated_weekly_units = sales.weekly_units
            existing.sales_estimate_source = sales.source
            existing.raw_json = enriched.raw
            synced += 1

            record_credit_usage(
                db,
                used=enriched.credit_used,
                remaining_reported=client.last_credits_remaining,
                settings=settings,
            )

        sync_run.status = "success"
        sync_run.products_synced = synced
        sync_run.credits_used = credits_this_run
        sync_run.credits_remaining = client.last_credits_remaining
        sync_run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(sync_run)
        return sync_run

    except CreditBudgetExceeded as exc:
        sync_run.status = "budget_exceeded"
        sync_run.error_message = str(exc)
        sync_run.products_synced = synced
        sync_run.credits_used = credits_this_run
        sync_run.credits_remaining = client.last_credits_remaining
        sync_run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(sync_run)
        return sync_run
    except Exception as exc:  # noqa: BLE001
        sync_run.status = "failed"
        sync_run.error_message = str(exc)
        sync_run.products_synced = synced
        sync_run.credits_used = credits_this_run
        sync_run.credits_remaining = client.last_credits_remaining
        sync_run.finished_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(sync_run)
        return sync_run


def build_sync_status(db: Session, category_id: int | None, settings: Settings):
    from app.schemas import CreditStatus, SyncStatus

    query = select(SyncRun).order_by(SyncRun.started_at.desc())
    if category_id is not None:
        query = query.where(SyncRun.category_id == category_id)
    last = db.scalar(query.limit(1))
    credits = credit_status(db, settings)
    return SyncStatus(
        last_sync_at=last.finished_at or last.started_at if last else None,
        last_status=last.status if last else None,
        last_week_start=last.week_start if last else None,
        last_products_synced=last.products_synced if last else None,
        last_error=last.error_message if last else None,
        credits=CreditStatus(**credits),
    )
