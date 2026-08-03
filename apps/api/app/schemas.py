from datetime import date, datetime

from pydantic import BaseModel, Field


class CategoryOut(BaseModel):
    id: int
    slug: str
    name: str
    bestsellers_url: str

    model_config = {"from_attributes": True}


class CreditStatus(BaseModel):
    monthly_budget: int
    credits_used: int
    credits_remaining_budget: int
    credits_remaining_reported: int | None = None
    month_key: str


class SyncStatus(BaseModel):
    last_sync_at: datetime | None = None
    last_status: str | None = None
    last_week_start: date | None = None
    last_products_synced: int | None = None
    last_error: str | None = None
    credits: CreditStatus


class TopProductOut(BaseModel):
    rank: int
    asin: str
    title: str | None = None
    image_url: str | None = None
    brand: str | None = None
    product_url: str | None = None
    price: float | None = None
    currency: str | None = "GBP"
    price_change_absolute: float | None = None
    price_change_percent: float | None = None
    estimated_weekly_units: float | None = None
    sales_estimate_source: str | None = None
    bsr: int | None = None
    rating: float | None = None
    review_count: int | None = None
    monthly_sold: int | None = None


class CategoryTopOut(BaseModel):
    category: CategoryOut
    window: str = "7d"
    week_start: date | None = None
    as_of: datetime | None = None
    price_history_ready: bool = False
    note: str | None = None
    products: list[TopProductOut] = Field(default_factory=list)
    sync: SyncStatus


class SyncTriggerOut(BaseModel):
    status: str
    message: str
    week_start: date
    products_synced: int = 0
    credits_used: int = 0
    credits_remaining_budget: int | None = None


class FeaturedProductAddIn(BaseModel):
    input: str = Field(min_length=1)


class FeaturedProductAddOut(BaseModel):
    status: str
    message: str
    asin: str | None = None
    title: str | None = None
    rank: int | None = None
    credits_used: int = 0
    credits_remaining_budget: int | None = None
    week_start: date | None = None
