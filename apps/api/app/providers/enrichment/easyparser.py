from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings


class CreditBudgetExceeded(RuntimeError):
    pass


@dataclass
class EnrichedProduct:
    asin: str
    title: str | None
    image_url: str | None
    brand: str | None
    product_url: str | None
    price: float | None
    currency: str | None
    bsr: int | None
    rating: float | None
    review_count: int | None
    monthly_sold: int | None
    raw: dict[str, Any]
    credit_used: int
    credits_remaining: int | None


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace(",", "").replace("£", "").replace("$", "").strip()
        match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if match:
            return float(match.group(0))
    if isinstance(value, dict):
        for key in ("value", "amount", "raw"):
            if key in value:
                return _as_float(value[key])
    return None


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        digits = re.sub(r"[^\d]", "", value)
        if digits:
            return int(digits)
    if isinstance(value, dict):
        for key in ("value", "raw", "rank"):
            if key in value:
                return _as_int(value[key])
    return None


def _first_present(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, "", []):
            return data[key]
    return None


def _extract_bsr(payload: dict[str, Any]) -> int | None:
    flat = payload.get("bestsellers_rank_flat")
    if isinstance(flat, str):
        match = re.search(r"Rank:\s*([\d,]+)", flat)
        if match:
            return _as_int(match.group(1))

    ranks = payload.get("bestsellers_rank") or payload.get("bestSellersRank")
    if isinstance(ranks, list) and ranks:
        first = ranks[0]
        if isinstance(first, dict):
            return _as_int(first.get("rank") or first.get("value"))
        return _as_int(first)

    return _as_int(
        _first_present(payload, ["bsr", "salesRank", "sales_rank", "bestSellerRank"])
    )


def _extract_monthly_sold(payload: dict[str, Any]) -> int | None:
    direct = _as_int(
        _first_present(
            payload,
            [
                "boughtPastMonth",
                "bought_past_month",
                "monthlySold",
                "monthly_sold",
                "purchasesLast30Days",
                "purchases_last_30_days",
            ],
        )
    )
    if direct is not None:
        return direct

    # Phrases like "10K+ bought in past month"
    for key in ("boughtPastMonthText", "salesVolume", "unitSold"):
        text = payload.get(key)
        if isinstance(text, str):
            match = re.search(r"([\d,.]+)\s*([KkMm])?", text)
            if match:
                number = float(match.group(1).replace(",", ""))
                suffix = (match.group(2) or "").upper()
                if suffix == "K":
                    number *= 1000
                elif suffix == "M":
                    number *= 1_000_000
                return int(number)
    return None


def _extract_image(payload: dict[str, Any]) -> str | None:
    image = _first_present(payload, ["image", "mainImage", "main_image", "imageUrl"])
    if isinstance(image, str):
        return image
    if isinstance(image, dict):
        return image.get("url") or image.get("link")
    images = payload.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("url") or first.get("link")
    return None


def parse_detail_payload(asin: str, body: dict[str, Any]) -> EnrichedProduct:
    result = body.get("result") if isinstance(body.get("result"), dict) else body
    if not isinstance(result, dict):
        result = {}

    price = _as_float(
        _first_present(result, ["price", "priceValue", "currentPrice", "buyBoxPrice"])
    )
    currency = _first_present(result, ["currency", "currencyCode"])
    if isinstance(currency, dict):
        currency = currency.get("code") or currency.get("symbol")

    rating = _as_float(_first_present(result, ["rating", "stars", "averageRating"]))
    review_count = _as_int(
        _first_present(result, ["reviewCount", "reviewsCount", "ratingsTotal", "reviews"])
    )

    title = _first_present(result, ["title", "name", "productTitle"])
    brand = _first_present(result, ["brand", "brandName"])
    product_url = _first_present(result, ["url", "link", "productUrl"])
    if not product_url:
        product_url = f"https://www.amazon.co.uk/dp/{asin}"

    credit_used = _as_int(
        _first_present(
            body,
            ["credit_used_this_request", "credit_used", "credits_used_this_request"],
        )
    ) or 1
    credits_remaining = _as_int(
        _first_present(body, ["credits_remaining", "credit_remaining"])
    )

    return EnrichedProduct(
        asin=asin,
        title=str(title) if title else None,
        image_url=_extract_image(result),
        brand=str(brand) if brand else None,
        product_url=str(product_url) if product_url else None,
        price=price,
        currency=str(currency) if currency else "GBP",
        bsr=_extract_bsr(result),
        rating=rating,
        review_count=review_count,
        monthly_sold=_extract_monthly_sold(result),
        raw=body,
        credit_used=credit_used,
        credits_remaining=credits_remaining,
    )


class EasyparserClient:
    def __init__(self, settings: Settings, *, credits_used_this_month: int = 0):
        self.settings = settings
        self.credits_used_this_month = credits_used_this_month
        self.last_credits_remaining: int | None = None

    def remaining_budget(self) -> int:
        return max(0, self.settings.monthly_credit_budget - self.credits_used_this_month)

    def ensure_budget(self, needed: int = 1) -> None:
        if self.remaining_budget() < needed:
            raise CreditBudgetExceeded(
                f"Need {needed} credits but only {self.remaining_budget()} remain "
                f"in the monthly budget of {self.settings.monthly_credit_budget}."
            )

    def get_detail(self, asin: str) -> EnrichedProduct:
        if not self.settings.easyparser_api_key:
            raise RuntimeError("EASYPARSER_API_KEY is not configured")

        self.ensure_budget(1)
        params = {
            "api_key": self.settings.easyparser_api_key,
            "platform": "AMZ",
            "operation": "DETAIL",
            "domain": self.settings.amazon_domain,
            "asin": asin,
            "output": "json",
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.get(self.settings.easyparser_base_url, params=params)
            response.raise_for_status()
            body = response.json()

        enriched = parse_detail_payload(asin, body)
        self.credits_used_this_month += enriched.credit_used
        if enriched.credits_remaining is not None:
            self.last_credits_remaining = enriched.credits_remaining
        return enriched
