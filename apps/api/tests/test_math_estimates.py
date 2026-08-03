from datetime import date

from app.math_estimates import estimate_weekly_units, price_change, week_start_for


def test_estimate_prefers_monthly_sold():
    result = estimate_weekly_units(monthly_sold=430, bsr=100)
    assert result.source == "monthly_sold"
    assert result.weekly_units == 100.0


def test_estimate_falls_back_to_bsr_curve():
    result = estimate_weekly_units(monthly_sold=None, bsr=1000)
    assert result.source == "bsr_curve"
    assert result.weekly_units is not None
    assert result.weekly_units > 0


def test_estimate_unavailable_without_signals():
    result = estimate_weekly_units(None, None)
    assert result.source == "unavailable"
    assert result.weekly_units is None


def test_price_change_absolute_and_percent():
    delta = price_change(22.0, 20.0)
    assert delta.absolute == 2.0
    assert delta.percent == 10.0


def test_price_change_missing_previous():
    delta = price_change(22.0, None)
    assert delta.absolute is None
    assert delta.percent is None


def test_week_start_is_monday():
    assert week_start_for(date(2026, 8, 5)) == date(2026, 8, 3)  # Wednesday -> Monday
