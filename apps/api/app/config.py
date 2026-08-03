from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    easyparser_api_key: str = ""
    # SQLite by default so the MVP runs without Docker; use Postgres via docker-compose in prod.
    database_url: str = "sqlite:///./amazon_pulse.db"
    monthly_credit_budget: int = 100
    sync_top_n: int = 10
    api_cors_origins: str = "http://localhost:3000"
    easyparser_base_url: str = "https://realtime.easyparser.com/v1/request"
    amazon_domain: str = ".co.uk"
    amazon_marketplace_host: str = "www.amazon.co.uk"


@lru_cache
def get_settings() -> Settings:
    return Settings()
