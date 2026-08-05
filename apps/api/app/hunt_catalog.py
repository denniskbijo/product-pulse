"""Season → product-type catalog for Winter Hunt MVP (UK-focused)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductType:
    slug: str
    name: str
    description: str
    search_keyword: str


@dataclass(frozen=True)
class Season:
    slug: str
    name: str
    blurb: str
    product_types: tuple[ProductType, ...]


WINTER = Season(
    slug="winter",
    name="Winter",
    blurb=(
        "Explore product types that fit cold-weather and festive demand. "
        "Results show current UK Amazon demand — not last December’s archive."
    ),
    product_types=(
        ProductType(
            slug="home-heating",
            name="Home heating & warmth",
            description="Portable heaters, radiators, and room warmth.",
            search_keyword="space heater",
        ),
        ProductType(
            slug="sleep-bedding",
            name="Sleep & bedding comfort",
            description="Electric blankets, heated throws, warm bedding.",
            search_keyword="electric blanket",
        ),
        ProductType(
            slug="air-quality",
            name="Air quality",
            description="Humidifiers and dehumidifiers for closed-up homes.",
            search_keyword="humidifier",
        ),
        ProductType(
            slug="cold-weather-clothing",
            name="Cold-weather clothing",
            description="Gloves, thermals, and outer layers.",
            search_keyword="winter gloves",
        ),
        ProductType(
            slug="christmas-gifting",
            name="Christmas & gifting",
            description="Lights, calendars, and gift-season staples.",
            search_keyword="christmas tree lights",
        ),
        ProductType(
            slug="kitchen-comfort",
            name="Kitchen comfort",
            description="Soup makers, hot-drink helpers, winter kitchen gear.",
            search_keyword="soup maker",
        ),
        ProductType(
            slug="draft-insulation",
            name="Drafts & insulation",
            description="Draft excluders and simple heat-loss fixes.",
            search_keyword="draft excluder",
        ),
        ProductType(
            slug="personal-warmth",
            name="Personal warmth",
            description="Hot water bottles and portable personal heat.",
            search_keyword="hot water bottle",
        ),
    ),
)

SEASONS: dict[str, Season] = {WINTER.slug: WINTER}

HUNT_TOP_N = 5
HUNT_RUNS_TO_KEEP = 20


def list_seasons() -> list[Season]:
    return list(SEASONS.values())


def get_season(slug: str) -> Season | None:
    return SEASONS.get(slug.strip().lower())


def get_product_type(season_slug: str, type_slug: str) -> ProductType | None:
    season = get_season(season_slug)
    if season is None:
        return None
    for product_type in season.product_types:
        if product_type.slug == type_slug:
            return product_type
    return None
