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
    # Comma-separated. Use "*" for public demos / Vercel frontends.
    api_cors_origins: str = "http://localhost:3000"
    easyparser_base_url: str = "https://realtime.easyparser.com/v1/request"
    amazon_domain: str = ".co.uk"
    amazon_marketplace_host: str = "www.amazon.co.uk"

    # Auth (env-configured accounts; passwords compared as plain secrets)
    jwt_secret: str = ""
    jwt_expire_hours: int = 72
    admin_username: str = "admin"
    admin_password: str = ""
    user_username: str = "basil"
    user_password: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
