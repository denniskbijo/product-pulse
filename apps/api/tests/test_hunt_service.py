from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import Base
from app.hunt import get_hunt_run, run_hunt
from app.models import HuntResult, HuntRun
from app.providers.enrichment.easyparser import SearchHit


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_run_hunt_persists_sorted_results(monkeypatch):
    db = _session()
    settings = Settings(
        easyparser_api_key="test-key",
        monthly_credit_budget=100,
        hunt_top_n=5,
        jwt_secret="x",
    )

    hits = [
        SearchHit(position=1, asin="B0LOW00001", title="Low", monthly_sold=100),
        SearchHit(position=2, asin="B0HIGH0002", title="High", monthly_sold=5000),
        SearchHit(position=3, asin="B0NONE0003", title="None", monthly_sold=None),
    ]

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.last_credits_remaining = 90

        def ensure_budget(self, needed: int = 1) -> None:
            return None

        def search_catalog(self, *, keyword: str, top_n: int = 5):
            assert keyword == "electric blanket"
            return hits[:top_n], 1

    monkeypatch.setattr("app.hunt.EasyparserClient", FakeClient)

    detail = run_hunt(
        db,
        season_slug="winter",
        product_type_slug="sleep-bedding",
        settings=settings,
        created_by="admin",
    )
    assert detail.status == "success"
    assert detail.credits_used == 1
    assert len(detail.results) == 3
    assert detail.results[0].asin == "B0HIGH0002"
    assert detail.results[-1].asin == "B0NONE0003"

    stored = get_hunt_run(db, detail.id)
    assert stored is not None
    assert "not historical december" in stored.disclaimer.lower()


def test_run_hunt_unknown_type():
    db = _session()
    settings = Settings(easyparser_api_key="k", jwt_secret="x")
    try:
        run_hunt(
            db,
            season_slug="winter",
            product_type_slug="not-a-type",
            settings=settings,
            created_by="admin",
        )
        raise AssertionError("expected LookupError")
    except LookupError:
        pass
