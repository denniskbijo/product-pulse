from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/config.py -> repo root is parents[3], api root is parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = Path(__file__).resolve().parents[1]
ENV_CANDIDATES = (
    REPO_ROOT / ".env",
    API_ROOT / ".env",
    Path(".env"),
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=tuple(str(p) for p in ENV_CANDIDATES if p.exists())
        or (str(REPO_ROOT / ".env"),),
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    easyparser_api_key: str = ""
    # SQLite by default so the MVP runs without Docker; use Postgres via docker-compose in prod.
    database_url: str = f"sqlite:///{API_ROOT / 'amazon_pulse.db'}"
    monthly_credit_budget: int = 100
    sync_top_n: int = 10
    # Seasonal Hunt candidates per run (Oxylabs only — no Easyparser fallback).
    hunt_top_n: int = 5
    # Oxylabs Web Scraper API (required for Hunt).
    # https://developers.oxylabs.io/products/web-scraper-api
    oxylabs_username: str = ""
    oxylabs_password: str = ""
    oxylabs_base_url: str = "https://realtime.oxylabs.io/v1/queries"
    # Usage stats API (remaining balance when /stats/limits is unavailable).
    oxylabs_stats_url: str = "https://data.oxylabs.io/v2/stats"
    # Hard monthly budget for hunt gating (reserved before each Oxylabs call).
    oxylabs_monthly_credit_budget: int = 1000
    # Amazon marketplace TLD for Oxylabs (co.uk, com, de, …).
    oxylabs_amazon_domain: str = "co.uk"
    # Daily Amazon mobile price scrape (local/cron). Hard cap to stay polite.
    daily_scrape_max: int = 10
    daily_scrape_delay_seconds: float = 1.5
    # Comma-separated allowlist. Do NOT use "*".
    # Example prod: https://product-pulse-six.vercel.app,http://localhost:3000
    api_cors_origins: str = "http://localhost:3000"
    easyparser_base_url: str = "https://realtime.easyparser.com/v1/request"
    amazon_domain: str = ".co.uk"
    amazon_marketplace_host: str = "www.amazon.co.uk"

    # Auth (bcrypt password hashes — generate with: python -c "from app.passwords import hash_password; print(hash_password('...'))")
    jwt_secret: str = ""
    jwt_expire_hours: int = 72
    admin_username: str = "admin"
    admin_password_hash: str = ""
    user_username: str = "basil"
    user_password_hash: str = ""
    # Legacy plaintext fields ignored for auth (kept so old env files don't crash Settings).
    admin_password: str = ""
    user_password: str = ""

    # Vercel Cron / external schedulers: Authorization: Bearer <CRON_SECRET>
    cron_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
