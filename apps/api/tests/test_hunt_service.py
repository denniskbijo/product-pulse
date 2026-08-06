from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db import Base
from app.hunt import get_hunt_run, promote_hunt_run_to_category, run_hunt
from app.models import Category, ProductSnapshot
from app.providers.enrichment.easyparser import SearchHit


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed_winter_hunt(db) -> None:
    db.add(
        Category(
            slug="winter-hunt",
            name="Winter Hunt",
            bestsellers_url="https://www.amazon.co.uk/",
        )
    )
    db.commit()


def test_run_hunt_requires_oxylabs():
    db = _session()
    _seed_winter_hunt(db)
    settings = Settings(oxylabs_username="", oxylabs_password="", jwt_secret="x")
    detail = run_hunt(
        db,
        season_slug="winter",
        product_type_slug="sleep-bedding",
        settings=settings,
        created_by="admin",
    )
    assert detail.status == "failed"
    assert "oxylabs" in (detail.error_message or "").lower()


def test_run_hunt_oxylabs_autosaves_category(monkeypatch):
    db = _session()
    _seed_winter_hunt(db)
    settings = Settings(
        oxylabs_username="user",
        oxylabs_password="pass",
        hunt_top_n=5,
        jwt_secret="x",
    )

    hits = [
        SearchHit(position=1, asin="B0LOW00001", title="Low", monthly_sold=100),
        SearchHit(position=2, asin="B0HIGH0002", title="High", monthly_sold=5000),
        SearchHit(position=3, asin="B0NONE0003", title="None", monthly_sold=None),
    ]

    class FakeOxylabs:
        def __init__(self, *args, **kwargs):
            pass

        def hunt_catalog(self, *, keyword: str, top_n: int = 5, browse_node=None):
            assert keyword == "electric blanket"
            return hits[:top_n], 1, "amazon_search"

    monkeypatch.setattr("app.hunt.OxylabsClient", FakeOxylabs)

    detail = run_hunt(
        db,
        season_slug="winter",
        product_type_slug="sleep-bedding",
        settings=settings,
        created_by="admin",
    )
    assert detail.status == "success"
    assert detail.provider == "oxylabs:amazon_search"
    assert detail.credits_used == 1
    assert detail.category_saved is True
    assert detail.category_slug == "winter-hunt"
    assert len(detail.results) == 3
    assert detail.results[0].asin == "B0HIGH0002"

    snaps = db.scalars(select(ProductSnapshot)).all()
    assert len(snaps) == 3

    stored = get_hunt_run(db, detail.id)
    assert stored is not None
    assert "not historical december" in stored.disclaimer.lower() or "not historical" in stored.disclaimer.lower()


def test_run_hunt_unknown_type():
    db = _session()
    settings = Settings(oxylabs_username="u", oxylabs_password="p", jwt_secret="x")
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


def test_add_hunt_result_to_watchlist(monkeypatch):
    from app.hunt import add_hunt_result_to_watchlist
    from app.models import Category, ProductSnapshot

    db = _session()
    _seed_winter_hunt(db)
    db.add(
        Category(
            slug="watchlist",
            name="Watchlist",
            bestsellers_url="https://www.amazon.co.uk/",
        )
    )
    db.commit()

    settings = Settings(
        oxylabs_username="user",
        oxylabs_password="pass",
        hunt_top_n=5,
        jwt_secret="x",
    )
    hits = [
        SearchHit(
            position=1,
            asin="B0WATCH001",
            title="Watch me",
            monthly_sold=700,
            price=15.0,
        ),
    ]

    class FakeOxylabs:
        def __init__(self, *args, **kwargs):
            pass

        def hunt_catalog(self, *, keyword: str, top_n: int = 5, browse_node=None):
            return hits[:top_n], 1, "amazon_search"

    monkeypatch.setattr("app.hunt.OxylabsClient", FakeOxylabs)
    detail = run_hunt(
        db,
        season_slug="winter",
        product_type_slug="sleep-bedding",
        settings=settings,
        created_by="admin",
    )
    result = add_hunt_result_to_watchlist(db, run_id=detail.id, asin="B0WATCH001")
    assert result.status == "success"
    assert result.credits_used == 0
    watch = db.scalar(select(Category).where(Category.slug == "watchlist"))
    snaps = db.scalars(
        select(ProductSnapshot).where(ProductSnapshot.category_id == watch.id)
    ).all()
    assert len(snaps) == 1
    assert snaps[0].asin == "B0WATCH001"


def test_promote_hunt_run_to_category(monkeypatch):
    db = _session()
    _seed_winter_hunt(db)

    settings = Settings(
        oxylabs_username="user",
        oxylabs_password="pass",
        hunt_top_n=5,
        jwt_secret="x",
    )
    hits = [
        SearchHit(position=1, asin="B0PROM0001", title="Promo", monthly_sold=400, price=12.5),
        SearchHit(position=2, asin="B0PROM0002", title="Promo2", monthly_sold=900, price=20.0),
    ]

    class FakeOxylabs:
        def __init__(self, *args, **kwargs):
            pass

        def hunt_catalog(self, *, keyword: str, top_n: int = 5, browse_node=None):
            return hits[:top_n], 1, "amazon_search"

    monkeypatch.setattr("app.hunt.OxylabsClient", FakeOxylabs)
    detail = run_hunt(
        db,
        season_slug="winter",
        product_type_slug="sleep-bedding",
        settings=settings,
        created_by="admin",
    )
    # Auto-save already ran; manual promote should update.
    result = promote_hunt_run_to_category(db, run_id=detail.id)
    assert result.status == "success"
    assert result.products_updated == 2
    assert result.category_slug == "winter-hunt"
