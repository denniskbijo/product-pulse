from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.models import Category
from app.routers import categories
from app.seed import seed_categories
from app.sync import run_category_sync

scheduler = BackgroundScheduler()


def _weekly_sync_job() -> None:
    settings = get_settings()
    if not settings.easyparser_api_key:
        return
    db = SessionLocal()
    try:
        cats = db.scalars(select(Category).order_by(Category.id.asc())).all()
        # Free-tier default: sync only the first seeded category weekly.
        if cats:
            run_category_sync(db, cats[0], settings=settings)
    except Exception:  # noqa: BLE001
        # Scheduler should not crash the API process.
        pass
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    db = SessionLocal()
    try:
        seed_categories(db)
    finally:
        db.close()

    if not scheduler.running:
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(categories.router)


@app.get("/health")
def health():
    return {"ok": True}
