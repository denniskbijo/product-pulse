"""Sales volume and price-change helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


# Rough UK Home & Kitchen power-curve coefficients for BSR → daily units.
# sales_per_day ≈ a * BSR^(-b). Tuned for relative comparisons, not precision.
UK_HOME_KITCHEN_A = 8500.0
UK_HOME_KITCHEN_B = 0.875
WEEKS_PER_MONTH = 4.3


@dataclass(frozen=True)
class SalesEstimate:
    weekly_units: float | None
    source: str  # monthly_sold | bsr_curve | unavailable


@dataclass(frozen=True)
class PriceChange:
    absolute: float | None
    percent: float | None


def estimate_weekly_units(
    monthly_sold: int | None,
    bsr: int | None,
    *,
    curve_a: float = UK_HOME_KITCHEN_A,
    curve_b: float = UK_HOME_KITCHEN_B,
) -> SalesEstimate:
    if monthly_sold is not None and monthly_sold > 0:
        return SalesEstimate(
            weekly_units=round(monthly_sold / WEEKS_PER_MONTH, 1),
            source="monthly_sold",
        )

    if bsr is not None and bsr > 0:
        daily = curve_a * (bsr**-curve_b)
        weekly = daily * 7.0
        return SalesEstimate(weekly_units=round(weekly, 1), source="bsr_curve")

    return SalesEstimate(weekly_units=None, source="unavailable")


def price_change(current: float | None, previous: float | None) -> PriceChange:
    if current is None or previous is None:
        return PriceChange(absolute=None, percent=None)

    absolute = round(current - previous, 2)
    if previous == 0:
        return PriceChange(absolute=absolute, percent=None)

    percent = round((absolute / previous) * 100.0, 2)
    return PriceChange(absolute=absolute, percent=percent)


def week_start_for(d: date) -> date:
    """Monday-based ISO week start for a given date."""
    return d - timedelta(days=d.weekday())
