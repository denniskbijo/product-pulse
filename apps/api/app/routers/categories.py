from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import Category
from app.schemas import CategoryOut, CategoryTopOut, SyncStatus, SyncTriggerOut
from app.services import get_category_top, resolve_category
from app.sync import build_sync_status, run_category_sync

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)) -> list[Category]:
    return list(db.scalars(select(Category).order_by(Category.name.asc())).all())


@router.get("/status", response_model=SyncStatus)
def global_sync_status(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SyncStatus:
    return build_sync_status(db, None, settings)


@router.get("/{category_id}/top", response_model=CategoryTopOut)
def category_top(
    category_id: str,
    window: str = Query(default="7d"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CategoryTopOut:
    category = resolve_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return get_category_top(db, category, settings, window=window)


@router.post("/{category_id}/sync", response_model=SyncTriggerOut)
def trigger_sync(
    category_id: str,
    top_n: int | None = Query(
        default=None,
        ge=1,
        le=50,
        description="How many bestsellers to enrich. Use 1 to spend a single Easyparser DETAIL credit.",
    ),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SyncTriggerOut:
    category = resolve_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    count = top_n if top_n is not None else settings.sync_top_n
    sync_run = run_category_sync(db, category, settings=settings, top_n=count)
    credits = build_sync_status(db, category.id, settings).credits

    if sync_run.status == "success":
        message = (
            f"Synced {sync_run.products_synced} product(s); "
            f"used {sync_run.credits_used} Easyparser credit(s)"
        )
    elif sync_run.status == "budget_exceeded":
        message = sync_run.error_message or "Monthly Easyparser credit budget exhausted"
    else:
        message = sync_run.error_message or "Sync failed"

    return SyncTriggerOut(
        status=sync_run.status,
        message=message,
        week_start=sync_run.week_start,
        products_synced=sync_run.products_synced,
        credits_used=sync_run.credits_used,
        credits_remaining_budget=credits.credits_remaining_budget,
    )
