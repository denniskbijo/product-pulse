from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import API_ROOT, get_settings


class Base(DeclarativeBase):
    pass


def _resolve_database_url(url: str) -> str:
    """Keep relative sqlite paths under apps/api even when cwd is the repo root."""
    if not url.startswith("sqlite:///"):
        return url
    raw = url.removeprefix("sqlite:///")
    path = Path(raw)
    if not path.is_absolute():
        path = (API_ROOT / path).resolve()
    return f"sqlite:///{path}"


settings = get_settings()
database_url = _resolve_database_url(settings.database_url)
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(
    database_url,
    pool_pre_ping=not database_url.startswith("sqlite"),
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_columns() -> None:
    """Add columns that create_all will not alter onto existing tables."""
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "products" in tables:
        columns = {col["name"] for col in inspector.get_columns("products")}
        if "notes" not in columns:
            with engine.begin() as conn:
                conn.execute(text("ALTER TABLE products ADD COLUMN notes TEXT"))
    if "hunt_runs" in tables:
        columns = {col["name"] for col in inspector.get_columns("hunt_runs")}
        if "provider" not in columns:
            with engine.begin() as conn:
                conn.execute(
                    text("ALTER TABLE hunt_runs ADD COLUMN provider VARCHAR(64)")
                )


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_columns()
