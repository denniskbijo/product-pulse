from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import AuthUser, get_current_user, require_admin
from app.config import Settings, get_settings
from app.credits import credit_status
from app.db import get_db
from app.hunt import get_hunt_run, list_hunt_runs, run_hunt
from app.hunt_catalog import HUNT_TOP_N, list_seasons
from app.schemas import (
    HuntProductTypeOut,
    HuntRunCreateIn,
    HuntRunDetailOut,
    HuntRunSummaryOut,
    HuntSeasonOut,
)

router = APIRouter(prefix="/hunt", tags=["hunt"])


@router.get("/seasons", response_model=list[HuntSeasonOut])
def hunt_seasons(_: AuthUser = Depends(get_current_user)) -> list[HuntSeasonOut]:
    return [
        HuntSeasonOut(
            slug=season.slug,
            name=season.name,
            blurb=season.blurb,
            product_types=[
                HuntProductTypeOut(
                    slug=pt.slug,
                    name=pt.name,
                    description=pt.description,
                )
                for pt in season.product_types
            ],
        )
        for season in list_seasons()
    ]


@router.get("/runs", response_model=list[HuntRunSummaryOut])
def hunt_runs(
    db: Session = Depends(get_db),
    _: AuthUser = Depends(get_current_user),
) -> list[HuntRunSummaryOut]:
    return list_hunt_runs(db)


@router.get("/runs/{run_id}", response_model=HuntRunDetailOut)
def hunt_run_detail(
    run_id: int,
    db: Session = Depends(get_db),
    user: AuthUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> HuntRunDetailOut:
    detail = get_hunt_run(db, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Hunt run not found")
    if user.role == "admin":
        detail.credits_remaining_budget = credit_status(db, settings)[
            "credits_remaining_budget"
        ]
    return detail


@router.post("/runs", response_model=HuntRunDetailOut)
def create_hunt_run(
    body: HuntRunCreateIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: AuthUser = Depends(require_admin),
) -> HuntRunDetailOut:
    try:
        return run_hunt(
            db,
            season_slug=body.season_slug,
            product_type_slug=body.product_type_slug,
            settings=settings,
            created_by=user.username,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/meta")
def hunt_meta(_: AuthUser = Depends(get_current_user)) -> dict:
    return {
        "top_n": HUNT_TOP_N,
        "credits_per_hunt": 1,
        "disclaimer": (
            "Current UK demand from Amazon search — not historical December "
            "bestsellers or multi-year winter sales."
        ),
    }
