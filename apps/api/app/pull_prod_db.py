"""Copy production Postgres tables into the local DATABASE_URL (usually SQLite)."""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.engine import Engine

from app.config import API_ROOT, REPO_ROOT, get_settings
from app.models import (  # noqa: F401 — register metadata
    Category,
    CreditLedger,
    DailyPricePoint,
    Product,
    ProductSnapshot,
    SyncRun,
)
from app.db import Base

# FK-safe copy order.
TABLE_ORDER = [
    "categories",
    "products",
    "product_snapshots",
    "daily_price_points",
    "sync_runs",
    "credit_ledger",
]


def _normalize_sqlalchemy_url(url: str) -> str:
    url = url.strip().strip('"').strip("'")
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://") and "+psycopg" not in url:
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _redact(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.password:
        return url
    netloc = parsed.netloc.replace(f":{parsed.password}", ":****")
    return parsed._replace(netloc=netloc).geturl()


def _sqlite_path(url: str) -> Path | None:
    if not url.startswith("sqlite:///"):
        return None
    raw = url.removeprefix("sqlite:///")
    path = Path(raw)
    if not path.is_absolute():
        # Resolve relative to API root so make db-pull / make run share one file.
        path = (API_ROOT / path).resolve()
    return path


def _canonicalize_target_url(url: str) -> str:
    """Point relative sqlite:/// paths at apps/api regardless of process cwd."""
    path = _sqlite_path(url)
    if path is None:
        return url
    return f"sqlite:///{path}"


def _looks_like_db_url(value: str) -> bool:
    lowered = value.lower()
    if not value or value in {"[SENSITIVE]", "sensitive"}:
        return False
    return lowered.startswith(
        ("postgres://", "postgresql://", "postgresql+psycopg://", "sqlite:///")
    )


def _fetch_prod_url_from_vercel() -> str | None:
    """Pull production DATABASE_URL via Vercel CLI if available.

    Note: Vercel "Sensitive" env vars are pulled as the literal [SENSITIVE] and
    cannot be read by the CLI/API. Prefer PROD_DATABASE_URL in that case.
    """
    api_dir = API_ROOT
    if not (api_dir / ".vercel" / "project.json").exists():
        return None
    try:
        result = subprocess.run(
            [
                "npx",
                "--yes",
                "vercel@latest",
                "env",
                "pull",
                ".env.vercel.prod.tmp",
                "--environment",
                "production",
                "--yes",
            ],
            cwd=api_dir,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    env_path = api_dir / ".env.vercel.prod.tmp"
    if result.returncode != 0 or not env_path.exists():
        return None

    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("DATABASE_URL="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if _looks_like_db_url(value):
                    return value
                return None
    finally:
        env_path.unlink(missing_ok=True)
    return None


def _fetch_prod_url_from_neonctl() -> str | None:
    """Use neonctl if logged in (project name product-pulse)."""
    project = os.getenv("NEON_PROJECT_ID", "small-fire-19232450").strip()
    try:
        result = subprocess.run(
            [
                "npx",
                "--yes",
                "neonctl@latest",
                "connection-string",
                "--project-id",
                project,
                "--role-name",
                "neondb_owner",
                "--database-name",
                "neondb",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    if not lines:
        return None
    value = lines[-1]
    return value if _looks_like_db_url(value) else None


def resolve_prod_database_url() -> str:
    for key in ("PROD_DATABASE_URL", "DATABASE_URL_PROD"):
        value = os.getenv(key, "").strip()
        if _looks_like_db_url(value):
            return _normalize_sqlalchemy_url(value)

    pulled = _fetch_prod_url_from_vercel()
    if pulled:
        return _normalize_sqlalchemy_url(pulled)

    neon = _fetch_prod_url_from_neonctl()
    if neon:
        return _normalize_sqlalchemy_url(neon)

    raise SystemExit(
        "No usable production DATABASE_URL found.\n\n"
        "Tried PROD_DATABASE_URL, Vercel env pull, and neonctl.\n"
        "Vercel Sensitive env vars cannot be read by the CLI.\n\n"
        "Fix options:\n"
        "  1) Add PROD_DATABASE_URL to repo-root .env (do not commit), or\n"
        "  2) Login with neonctl (`npx neonctl auth`) for project product-pulse.\n"
    )


def _engine(url: str, *, sqlite: bool = False) -> Engine:
    connect_args = {"check_same_thread": False} if sqlite or url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=not url.startswith("sqlite"), connect_args=connect_args)


def _backup_sqlite(path: Path) -> Path | None:
    if not path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"{path.stem}.backup-{stamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def _row_to_dict(row_mapping) -> dict:
    data = dict(row_mapping)
    for key, value in list(data.items()):
        # SQLite is happier with naive UTC timestamps from aware APIs.
        if hasattr(value, "tzinfo") and value.tzinfo is not None:
            data[key] = value.astimezone(timezone.utc).replace(tzinfo=None)
    return data


def copy_database(*, source_url: str, target_url: str) -> dict[str, int]:
    source = _engine(source_url)
    target = _engine(target_url)

    # Ensure local schema exists.
    Base.metadata.create_all(bind=target)

    counts: dict[str, int] = {}
    src_meta = MetaData()
    src_meta.reflect(bind=source)

    with source.connect() as src_conn, target.begin() as dst_conn:
        # Disable FK checks while replacing data (SQLite).
        if target_url.startswith("sqlite"):
            dst_conn.execute(text("PRAGMA foreign_keys=OFF"))

        for table_name in reversed(TABLE_ORDER):
            if table_name in Base.metadata.tables:
                dst_conn.execute(text(f"DELETE FROM {table_name}"))

        for table_name in TABLE_ORDER:
            table = src_meta.tables.get(table_name)
            if table is None:
                counts[table_name] = 0
                continue
            rows = src_conn.execute(table.select()).mappings().all()
            dest_table = Base.metadata.tables[table_name]
            payload = [_row_to_dict(row) for row in rows]
            if payload:
                dst_conn.execute(dest_table.insert(), payload)
            counts[table_name] = len(payload)

        if target_url.startswith("sqlite"):
            dst_conn.execute(text("PRAGMA foreign_keys=ON"))

    source.dispose()
    target.dispose()
    return counts


def run_pull() -> int:
    settings = get_settings()
    target_url = _canonicalize_target_url(_normalize_sqlalchemy_url(settings.database_url))
    source_url = resolve_prod_database_url()

    if source_url == target_url:
        raise SystemExit("PROD and local DATABASE_URL are the same — refusing to overwrite.")

    sqlite_path = _sqlite_path(target_url)
    backup = _backup_sqlite(sqlite_path) if sqlite_path else None

    print(f"Source : {_redact(source_url)}")
    print(f"Target : {_redact(target_url)}")
    if backup:
        print(f"Backup : {backup}")

    counts = copy_database(source_url=source_url, target_url=target_url)
    total = sum(counts.values())
    print("Copied rows:")
    for name in TABLE_ORDER:
        print(f"  {name}: {counts.get(name, 0)}")
    print(f"Total: {total}")
    print(f"Done. Local DB ready (repo root hint: {REPO_ROOT})")
    return 0
