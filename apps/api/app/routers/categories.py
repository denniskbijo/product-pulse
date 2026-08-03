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
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SyncTriggerOut:
    category = resolve_category(db, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    try:
        sync_run = run_category_sync(db, category, settings=settings)
    except Exception as exc:  # noqa: BLE001
        # Failed runs are persisted; surface a useful error.
        status = build_sync_status(db, category.id, settings)
        raise HTTPException(
            status_code=502,
            detail={
                "message": str(exc),
                "sync": status.model_dump(mode="json"),
            },
        ) from exc

    credits = build_sync_status(db, category.id, settings).credits
    message = {
        "success": "Sync completed",
        "budget_exceeded": "Stopped early: monthly Easyparser credit budget exhausted",
        "failed": sync_run.error_message or "Sync failed",
    }.get(sync_run.status, sync_run.status)

    return SyncTriggerOut(
        status=sync_run.status,
        message=message,
        week_start=sync_run.week_start,
        products_synced=sync_run.products_synced,
        credits_used=sync_run.credits_used,
        credits_remaining_budget=credits.credits_remaining_budget,
    )
