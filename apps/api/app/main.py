import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import Category
from app.routers import auth, categories, cron, hunt, products
from app.daily_prices import run_daily_price_scrape
from app.seed import seed_categories
from app.sync import run_category_sync

scheduler = BackgroundScheduler()


def _running_on_serverless() -> bool:
    return bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))


def _weekly_sync_job() -> None:
    settings = get_settings()
    if not settings.easyparser_api_key:
        return
    db = SessionLocal()
    try:
        cats = db.scalars(select(Category).order_by(Category.id.asc())).all()
        # Free-tier default: sync first real bestsellers category (skip Watchlist).
        target = next((c for c in cats if c.slug != "watchlist"), None)
        if target is not None:
            run_category_sync(db, target, settings=settings)
    except Exception:  # noqa: BLE001
        # Scheduler should not crash the API process.
        pass
    finally:
        db.close()


def _daily_prices_job() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        run_daily_price_scrape(db, settings=settings)
    except Exception:  # noqa: BLE001
        pass
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_categories(db)
    except Exception:  # noqa: BLE001
        # Never block the whole API on a seed/migration hiccup.
        db.rollback()
    finally:
        db.close()

    # APScheduler is for local/long-running hosts only (not Vercel serverless).
    # Production daily prices use Vercel Cron → GET /cron/daily-prices.
    if not _running_on_serverless() and not scheduler.running:
        scheduler.add_job(
            _daily_prices_job,
            CronTrigger(hour=7, minute=0),
            id="daily_price_scrape",
            replace_existing=True,
        )
        scheduler.add_job(
            _weekly_sync_job,
            CronTrigger(day_of_week="mon", hour=6, minute=0),
            id="weekly_category_sync",
            replace_existing=True,
        )
        scheduler.start()
    yield
    if scheduler.running:
        scheduler.shutdown(wait=False)


settings = get_settings()
app = FastAPI(title="Amazon Pulse API", version="0.1.0", lifespan=lifespan)

origins = [o.strip() for o in settings.api_cors_origins.split(",") if o.strip()]
# Allow Vercel preview/production frontends when CORS is left open via *.
if "*" in origins:
    cors_origins = ["*"]
    allow_credentials = False
else:
    cors_origins = origins or ["http://localhost:3000"]
    allow_credentials = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(categories.router)
app.include_router(products.router)
app.include_router(cron.router)
app.include_router(hunt.router)


@app.get("/health")
def health():
    return {"ok": True}
