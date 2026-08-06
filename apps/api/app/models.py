from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    bestsellers_url: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    snapshots: Mapped[list["ProductSnapshot"]] = relationship(back_populates="category")
    sync_runs: Mapped[list["SyncRun"]] = relationship(back_populates="category")


class Product(Base):
    __tablename__ = "products"

    asin: Mapped[str] = mapped_column(String(16), primary_key=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    snapshots: Mapped[list["ProductSnapshot"]] = relationship(back_populates="product")
    daily_prices: Mapped[list["DailyPricePoint"]] = relationship(back_populates="product")


class DailyPricePoint(Base):
    """One observed price per ASIN per calendar day (Amazon mobile scrape)."""

    __tablename__ = "daily_price_points"
    __table_args__ = (
        UniqueConstraint("asin", "observed_on", name="uq_daily_price_asin_day"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asin: Mapped[str] = mapped_column(ForeignKey("products.asin"), index=True)
    observed_on: Mapped[date] = mapped_column(Date, index=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="amazon_mobile")
    status: Mapped[str] = mapped_column(String(32), default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    product: Mapped[Product] = relationship(back_populates="daily_prices")


class ProductSnapshot(Base):
    __tablename__ = "product_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "category_id", "asin", "week_start", name="uq_snapshot_category_asin_week"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    asin: Mapped[str] = mapped_column(ForeignKey("products.asin"), index=True)
    week_start: Mapped[date] = mapped_column(Date, index=True)
    rank: Mapped[int] = mapped_column(Integer)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    bsr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_sold: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_weekly_units: Mapped[float | None] = mapped_column(Float, nullable=True)
    sales_estimate_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    raw_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    category: Mapped[Category] = relationship(back_populates="snapshots")
    product: Mapped[Product] = relationship(back_populates="snapshots")


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id"), nullable=True, index=True
    )
    week_start: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    credits_used: Mapped[int] = mapped_column(Integer, default=0)
    credits_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    products_synced: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    category: Mapped[Category | None] = relationship(back_populates="sync_runs")


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month_key: Mapped[str] = mapped_column(String(7), unique=True, index=True)
    credits_used: Mapped[int] = mapped_column(Integer, default=0)
    credits_remaining_reported: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class HuntRun(Base):
    __tablename__ = "hunt_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_slug: Mapped[str] = mapped_column(String(64), index=True)
    product_type_slug: Mapped[str] = mapped_column(String(64), index=True)
    product_type_name: Mapped[str] = mapped_column(String(128))
    search_keyword: Mapped[str] = mapped_column(String(255))
    top_n: Mapped[int] = mapped_column(Integer, default=5)
    status: Mapped[str] = mapped_column(String(32), default="running")
    # easyparser | oxylabs | oxylabs:amazon_search | oxylabs:amazon_bestsellers
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    credits_used: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    results: Mapped[list["HuntResult"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class HuntResult(Base):
    __tablename__ = "hunt_results"
    __table_args__ = (
        UniqueConstraint("run_id", "asin", name="uq_hunt_result_run_asin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("hunt_runs.id"), index=True)
    search_position: Mapped[int] = mapped_column(Integer)
    asin: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    product_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    review_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    monthly_sold: Mapped[int | None] = mapped_column(Integer, nullable=True)

    run: Mapped[HuntRun] = relationship(back_populates="results")
