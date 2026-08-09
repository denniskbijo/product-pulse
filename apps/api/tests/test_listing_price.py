from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import Base
from app.listing_price import resolve_uk_listing_price, upsert_daily_price_point
from app.models import DailyPricePoint, Product
from app.providers.prices.amazon_mobile import MobilePriceResult


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_resolve_prefers_mobile_uk_price(monkeypatch):
    settings = Settings(amazon_marketplace_host="www.amazon.co.uk")

    def fake_mobile(asin, *, host="www.amazon.co.uk", timeout=30.0):
        return MobilePriceResult(
            asin=asin, status="success", price=50.99, currency="GBP"
        )

    monkeypatch.setattr("app.listing_price.fetch_mobile_price", fake_mobile)
    price, currency = resolve_uk_listing_price(
        "B0GV4558G7",
        fallback_price=66.11,
        fallback_currency="USD",
        settings=settings,
    )
    assert price == 50.99
    assert currency == "GBP"


def test_resolve_rejects_usd_fallback_when_mobile_fails(monkeypatch):
    settings = Settings(amazon_marketplace_host="www.amazon.co.uk")

    def fake_mobile(asin, *, host="www.amazon.co.uk", timeout=30.0):
        return MobilePriceResult(asin=asin, status="blocked", error="bot")

    monkeypatch.setattr("app.listing_price.fetch_mobile_price", fake_mobile)
    price, currency = resolve_uk_listing_price(
        "B0GV4558G7",
        fallback_price=66.11,
        fallback_currency="USD",
        settings=settings,
    )
    assert price is None
    assert currency is None


def test_resolve_keeps_gbp_easyparser_when_mobile_fails(monkeypatch):
    settings = Settings(amazon_marketplace_host="www.amazon.co.uk")

    def fake_mobile(asin, *, host="www.amazon.co.uk", timeout=30.0):
        return MobilePriceResult(asin=asin, status="parse_error", error="no price")

    monkeypatch.setattr("app.listing_price.fetch_mobile_price", fake_mobile)
    price, currency = resolve_uk_listing_price(
        "B0TESTASIN",
        fallback_price=12.5,
        fallback_currency="GBP",
        settings=settings,
    )
    assert price == 12.5
    assert currency == "GBP"


def test_upsert_daily_price_point():
    db = _session()
    upsert_daily_price_point(
        db, asin="B0TESTASIN", price=50.99, currency="GBP", observed_on=date(2026, 8, 9)
    )
    db.commit()
    row = db.scalar(
        select(DailyPricePoint).where(
            DailyPricePoint.asin == "B0TESTASIN",
            DailyPricePoint.observed_on == date(2026, 8, 9),
        )
    )
    assert row is not None
    assert row.price == 50.99
    assert row.currency == "GBP"
    assert row.status == "success"
    assert db.get(Product, "B0TESTASIN") is not None
