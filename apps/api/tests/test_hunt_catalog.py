from datetime import date

from app.hunt_catalog import (
    calendar_season_slug,
    default_hunt_season_slug,
    list_seasons,
)


def test_list_seasons_includes_all_four():
    slugs = [s.slug for s in list_seasons()]
    assert slugs == ["spring", "summer", "autumn", "winter"]


def test_calendar_and_default_hunt_seasons():
    assert calendar_season_slug(date(2026, 1, 15)) == "winter"
    assert default_hunt_season_slug(date(2026, 1, 15)) == "summer"

    assert calendar_season_slug(date(2026, 4, 1)) == "spring"
    assert default_hunt_season_slug(date(2026, 4, 1)) == "autumn"

    assert calendar_season_slug(date(2026, 7, 1)) == "summer"
    assert default_hunt_season_slug(date(2026, 7, 1)) == "winter"

    assert calendar_season_slug(date(2026, 10, 1)) == "autumn"
    assert default_hunt_season_slug(date(2026, 10, 1)) == "spring"
