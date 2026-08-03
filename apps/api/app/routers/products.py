from fastapi import APIRouter, Depends, HTTPException

from app.auth import AuthUser, get_current_user
from app.db import get_db
from app.schemas import ProductDetailOut
from app.services import get_product_detail
from sqlalchemy.orm import Session

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/{asin}", response_model=ProductDetailOut)
def product_detail(
    asin: str,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(get_current_user),
) -> ProductDetailOut:
    detail = get_product_detail(db, asin)
    if detail is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return detail
