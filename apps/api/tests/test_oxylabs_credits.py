from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import Base
from app.oxylabs_credits import (
    OxylabsBudgetExceeded,
    get_or_create_oxylabs_ledger,
    reserve_oxylabs_credit,
)
from app.providers.discovery.oxylabs import parse_monthly_results_used


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_parse_monthly_results_used():
    payload = {
        "data": [
            {
                "date": "2026-08",
                "products": [
                    {"title": "serp_scraper_api", "all_count": 0},
                    {"title": "ecommerce_scraper_api", "all_count": 2},
                    {"title": "web_scraper_api", "all_count": 0},
                ],
            }
        ]
    }
    assert parse_monthly_results_used(payload, month_key="2026-08") == 2
    assert parse_monthly_results_used(payload, month_key="2026-07") == 0


def test_reserve_oxylabs_credit_counts_and_blocks(monkeypatch):
    db = _session()
    settings = Settings(
        oxylabs_username="u",
        oxylabs_password="p",
        oxylabs_monthly_credit_budget=2,
    )

    class FakeOxylabs:
        def __init__(self, *args, **kwargs):
            pass

        def fetch_month_results_used(self, *, month_key: str):
            return None

    monkeypatch.setattr("app.oxylabs_credits.OxylabsClient", FakeOxylabs)

    first = reserve_oxylabs_credit(db, settings, amount=1)
    assert first.credits_used == 1
    second = reserve_oxylabs_credit(db, settings, amount=1)
    assert second.credits_used == 2
    try:
        reserve_oxylabs_credit(db, settings, amount=1)
        raise AssertionError("expected OxylabsBudgetExceeded")
    except OxylabsBudgetExceeded:
        pass
    ledger = get_or_create_oxylabs_ledger(db)
    assert ledger.credits_used == 2


def test_reserve_syncs_up_to_remote_usage(monkeypatch):
    db = _session()
    settings = Settings(
        oxylabs_username="u",
        oxylabs_password="p",
        oxylabs_monthly_credit_budget=10,
    )

    class FakeOxylabs:
        def __init__(self, *args, **kwargs):
            pass

        def fetch_month_results_used(self, *, month_key: str):
            return 7

    monkeypatch.setattr("app.oxylabs_credits.OxylabsClient", FakeOxylabs)
    ledger = reserve_oxylabs_credit(db, settings, amount=1)
    assert ledger.credits_used == 8
