"""Season → product-type catalog for Seasonal Hunt (UK-focused)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ProductType:
    slug: str
    name: str
    description: str
    search_keyword: str
    # Optional Amazon UK Best Sellers browse-node ID for Oxylabs amazon_bestsellers.
    # Leave empty to use amazon_search with search_keyword instead.
    bestsellers_browse_node: str = ""


@dataclass(frozen=True)
class Season:
    slug: str
    name: str
    blurb: str
    product_types: tuple[ProductType, ...]


SPRING = Season(
    slug="spring",
    name="Spring",
    blurb=(
        "Explore product types for spring demand — garden, allergy season, and "
        "outdoor living. Results show current UK Amazon demand, not last spring’s archive."
    ),
    product_types=(
        ProductType(
            slug="garden-outdoor",
            name="Garden & outdoor",
            description="Planters, tools, and outdoor kit for warmer days.",
            search_keyword="garden tools",
        ),
        ProductType(
            slug="allergy-air",
            name="Allergy & air",
            description="Air purifiers and allergy-season helpers.",
            search_keyword="air purifier",
        ),
        ProductType(
            slug="spring-cleaning",
            name="Spring cleaning",
            description="Cleaning tools and refresh staples.",
            search_keyword="steam cleaner",
        ),
        ProductType(
            slug="bbq-picnic",
            name="BBQ & picnic",
            description="Early outdoor cooking and picnic gear.",
            search_keyword="portable bbq",
        ),
        ProductType(
            slug="kids-outdoor",
            name="Kids outdoor",
            description="Outdoor play and garden toys.",
            search_keyword="kids outdoor toys",
        ),
    ),
)

SUMMER = Season(
    slug="summer",
    name="Summer",
    blurb=(
        "Explore cooling, sun, travel, and outdoor entertaining demand. "
        "Results show current UK Amazon demand — not last summer’s archive."
    ),
    product_types=(
        ProductType(
            slug="cooling-fans",
            name="Cooling & fans",
            description="Fans, coolers, and hot-weather comfort.",
            search_keyword="tower fan",
        ),
        ProductType(
            slug="sun-care",
            name="Sun care",
            description="Sunscreen and sun-protection staples.",
            search_keyword="sunscreen spf 50",
        ),
        ProductType(
            slug="camping-travel",
            name="Camping & travel",
            description="Camping kit and summer travel gear.",
            search_keyword="camping tent",
        ),
        ProductType(
            slug="pool-water",
            name="Pool & water",
            description="Paddling pools and water play.",
            search_keyword="paddling pool",
        ),
        ProductType(
            slug="outdoor-entertaining",
            name="Outdoor entertaining",
            description="Garden furniture and outdoor dining.",
            search_keyword="garden furniture set",
        ),
    ),
)

AUTUMN = Season(
    slug="autumn",
    name="Autumn",
    blurb=(
        "Explore back-to-school, layers, early heating, and autumn décor demand. "
        "Results show current UK Amazon demand — not last autumn’s archive."
    ),
    product_types=(
        ProductType(
            slug="back-to-school",
            name="Back to school",
            description="Bags, stationery, and school-run staples.",
            search_keyword="school backpack",
        ),
        ProductType(
            slug="halloween-decor",
            name="Halloween & autumn décor",
            description="Halloween and autumn home décor.",
            search_keyword="halloween decorations",
        ),
        ProductType(
            slug="coats-layers",
            name="Coats & layers",
            description="Jackets, waterproofs, and transitional layers.",
            search_keyword="waterproof jacket",
        ),
        ProductType(
            slug="early-heating",
            name="Home heating (early)",
            description="Early-season heaters and room warmth.",
            search_keyword="oil filled radiator",
        ),
        ProductType(
            slug="comfort-food-kitchen",
            name="Comfort food kitchen",
            description="Slow cookers, soup makers, and autumn kitchen gear.",
            search_keyword="slow cooker",
        ),
    ),
)

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

# Display order in the UI season picker.
SEASON_ORDER = ("spring", "summer", "autumn", "winter")

SEASONS: dict[str, Season] = {
    SPRING.slug: SPRING,
    SUMMER.slug: SUMMER,
    AUTUMN.slug: AUTUMN,
    WINTER.slug: WINTER,
}

# Current calendar season → default hunt season (procure ahead).
# Winter→Summer, Spring→Autumn, Summer→Winter, Autumn→Spring.
DEFAULT_HUNT_BY_CURRENT_SEASON: dict[str, str] = {
    "winter": "summer",
    "spring": "autumn",
    "summer": "winter",
    "autumn": "spring",
}

HUNT_TOP_N = 5
HUNT_RUNS_TO_KEEP = 20


def list_seasons() -> list[Season]:
    return [SEASONS[slug] for slug in SEASON_ORDER if slug in SEASONS]


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


def calendar_season_slug(today: date | None = None) -> str:
    """UK meteorological seasons: Spring Mar–May, Summer Jun–Aug, Autumn Sep–Nov, Winter Dec–Feb."""
    month = (today or date.today()).month
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "autumn"
    return "winter"


def default_hunt_season_slug(today: date | None = None) -> str:
    """Season to hunt by default so products can be procured ahead of peak demand."""
    current = calendar_season_slug(today)
    return DEFAULT_HUNT_BY_CURRENT_SEASON.get(current, "winter")
