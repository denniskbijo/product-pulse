from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import AuthUser, get_current_user
from app.db import get_db
from app.schemas import ProductDetailOut, ProductNotesIn, ProductNotesOut
from app.services import (
    HISTORY_WINDOW_DAYS_DEFAULT,
    HISTORY_WINDOW_DAYS_MAX,
    get_product_detail,
    update_product_notes,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{asin}", response_model=ProductDetailOut)
def product_detail(
    asin: str,
    history_days: int = Query(
        default=HISTORY_WINDOW_DAYS_DEFAULT, ge=1, le=HISTORY_WINDOW_DAYS_MAX
    ),
    history_end: date | None = None,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(get_current_user),
) -> ProductDetailOut:
    detail = get_product_detail(
        db, asin, history_days=history_days, history_end=history_end
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return detail


@router.patch("/{asin}", response_model=ProductNotesOut)
def patch_product_notes(
    asin: str,
    body: ProductNotesIn,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(get_current_user),
) -> ProductNotesOut:
    result = update_product_notes(db, asin, body.notes)
    if result is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return result
