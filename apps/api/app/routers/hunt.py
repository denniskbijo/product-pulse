from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import AuthUser, get_current_user, require_admin
from app.config import Settings, get_settings
from app.db import get_db
from app.hunt import (
    HUNT_CATEGORY_SLUG,
    OXYLABS_REQUESTS_PER_HUNT,
    add_hunt_result_to_watchlist,
    get_hunt_run,
    list_hunt_runs,
    promote_hunt_run_to_category,
    run_hunt,
)
from app.hunt_catalog import HUNT_TOP_N, list_seasons
from app.oxylabs_credits import oxylabs_credit_status
from app.providers.discovery.oxylabs import oxylabs_configured
from app.schemas import (
    HuntMetaOut,
    HuntProductTypeOut,
    HuntPromoteIn,
    HuntPromoteOut,
    HuntRunCreateIn,
    HuntRunDetailOut,
    HuntRunSummaryOut,
    HuntSeasonOut,
    OxylabsCreditsOut,
    WatchlistProductAddOut,
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
    _: AuthUser = Depends(get_current_user),
) -> HuntRunDetailOut:
    detail = get_hunt_run(db, run_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Hunt run not found")
    return detail


@router.post("/runs", response_model=HuntRunDetailOut)
def create_hunt_run(
    body: HuntRunCreateIn,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    user: AuthUser = Depends(get_current_user),
) -> HuntRunDetailOut:
    credits = oxylabs_credit_status(db, settings)
    if credits["configured"] and credits["credits_remaining"] < OXYLABS_REQUESTS_PER_HUNT:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Oxylabs monthly budget exhausted "
                f"({credits['credits_used']}/{credits['monthly_budget']} used)."
            ),
        )
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


@router.post(
    "/runs/{run_id}/results/{asin}/watchlist",
    response_model=WatchlistProductAddOut,
)
def add_hunt_asin_to_watchlist(
    run_id: int,
    asin: str,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(get_current_user),
) -> WatchlistProductAddOut:
    """Copy a hunt candidate into Watchlist using already-fetched hunt data (0 credits)."""
    try:
        return add_hunt_result_to_watchlist(db, run_id=run_id, asin=asin)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/runs/{run_id}/save-to-category", response_model=HuntPromoteOut)
def save_hunt_run_to_category(
    run_id: int,
    body: HuntPromoteIn | None = None,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_admin),
) -> HuntPromoteOut:
    """Manual re-publish (successful hunts already auto-save to Winter Hunt)."""
    payload = body or HuntPromoteIn()
    try:
        return promote_hunt_run_to_category(
            db,
            run_id=run_id,
            category_slug=payload.category_slug or HUNT_CATEGORY_SLUG,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/meta", response_model=HuntMetaOut)
def hunt_meta(
    db: Session = Depends(get_db),
    _: AuthUser = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> HuntMetaOut:
    credits = oxylabs_credit_status(db, settings)
    return HuntMetaOut(
        top_n=HUNT_TOP_N,
        provider="oxylabs",
        oxylabs_configured=oxylabs_configured(settings),
        uses_easyparser_credits=False,
        oxylabs_requests_per_hunt=OXYLABS_REQUESTS_PER_HUNT,
        auto_saves_to_category=True,
        anyone_can_hunt=True,
        disclaimer=(
            "Current UK demand from Oxylabs Amazon search/bestsellers — not "
            "historical December archives or multi-year winter sales."
        ),
        category_slug=HUNT_CATEGORY_SLUG,
        oxylabs_credits=OxylabsCreditsOut(**credits),
    )
