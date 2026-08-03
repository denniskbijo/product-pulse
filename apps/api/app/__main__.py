"""CLI entrypoints: python -m app scrape-prices | pull-prod-db"""

from __future__ import annotations

import argparse
import sys

from app.config import get_settings
from app.daily_prices import run_daily_price_scrape
from app.db import SessionLocal, init_db
from app.pull_prod_db import run_pull


def _cmd_scrape_prices(_: argparse.Namespace) -> int:
    settings = get_settings()
    init_db()
    db = SessionLocal()
    try:
        summary = run_daily_price_scrape(db, settings=settings)
    finally:
        db.close()

    print(
        f"Daily price scrape {summary.observed_on.isoformat()}: "
        f"requested={summary.requested} succeeded={summary.succeeded} "
        f"failed={summary.failed} max={settings.daily_scrape_max} "
        f"delay={settings.daily_scrape_delay_seconds}s"
    )
    if summary.asins:
        print("ASINs: " + ", ".join(summary.asins))
    else:
        print("No weekly snapshot ASINs found. Run a category sync first.")
        return 1
    return 0 if summary.succeeded > 0 or summary.requested == 0 else 2


def _cmd_pull_prod_db(_: argparse.Namespace) -> int:
    return run_pull()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app")
    sub = parser.add_subparsers(dest="command", required=True)

    scrape = sub.add_parser(
        "scrape-prices",
        help="Scrape Amazon mobile prices for up to N weekly-tracked ASINs (no Easyparser)",
    )
    scrape.set_defaults(func=_cmd_scrape_prices)

    pull = sub.add_parser(
        "pull-prod-db",
        help="Copy production Neon tables into local DATABASE_URL (backs up SQLite first)",
    )
    pull.set_defaults(func=_cmd_pull_prod_db)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
