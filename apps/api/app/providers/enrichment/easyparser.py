from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings
from app.providers.discovery.bestsellers_html import BestsellerEntry

ASIN_RE = re.compile(r"\b([A-Z0-9]{10})\b")
DP_RE = re.compile(r"/dp/([A-Z0-9]{10})")


class CreditBudgetExceeded(RuntimeError):
    pass


class EasyparserRequestError(RuntimeError):
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


@dataclass
class SearchHit:
    """One organic SEARCH result (no DETAIL credit)."""

    position: int
    asin: str
    title: str | None = None
    image_url: str | None = None
    brand: str | None = None
    product_url: str | None = None
    price: float | None = None
    currency: str | None = None
    rating: float | None = None
    review_count: int | None = None
    monthly_sold: int | None = None


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
        for key in ("value", "amount", "raw", "price"):
            if key in value:
                parsed = _as_float(value[key])
                if parsed is not None:
                    return parsed
    return None


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
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
                parsed = _as_int(value[key])
                if parsed is not None:
                    return parsed
    return None


def _first_present(data: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in data and data[key] not in (None, "", []):
            return data[key]
    return None


def _unwrap_product(body: dict[str, Any]) -> dict[str, Any]:
    result = body.get("result")
    if isinstance(result, dict):
        detail = result.get("detail")
        if isinstance(detail, dict):
            return detail
        return result
    return body if isinstance(body, dict) else {}


def _extract_bsr(payload: dict[str, Any]) -> int | None:
    ranks = (
        payload.get("bestsellers_rank")
        or payload.get("bestSellersRank")
        or payload.get("best_seller_rank")
        or payload.get("bestSellerRank")
    )
    if isinstance(ranks, list) and ranks:
        # Prefer root category rank (usually first).
        first = ranks[0]
        if isinstance(first, dict):
            return _as_int(first.get("rank") or first.get("value"))
        return _as_int(first)
    if isinstance(ranks, dict):
        return _as_int(ranks.get("rank") or ranks.get("value"))

    bestseller = payload.get("bestseller")
    if isinstance(bestseller, dict):
        rank = _as_int(bestseller.get("rank") or bestseller.get("value"))
        if rank is not None:
            return rank

    flat = payload.get("bestsellers_rank_flat")
    if isinstance(flat, str):
        match = re.search(r"Rank:\s*([\d,]+)", flat)
        if match:
            return _as_int(match.group(1))
    return None


def parse_bestsellers_rank_payload(body: dict[str, Any]) -> int | None:
    """Parse Easyparser BEST_SELLERS_RANK operation response."""
    result = body.get("result")
    if not isinstance(result, dict):
        return None
    product = result.get("product")
    if isinstance(product, dict):
        return _extract_bsr(product)
    return _extract_bsr(result)


def _extract_monthly_sold(payload: dict[str, Any]) -> int | None:
    activity = payload.get("bought_activity")
    if isinstance(activity, dict):
        value = _as_int(activity.get("value"))
        if value is not None:
            return value
        raw = activity.get("raw")
        if isinstance(raw, str):
            match = re.search(r"([\d,.]+)\s*([KkMm])?", raw)
            if match:
                number = float(match.group(1).replace(",", ""))
                suffix = (match.group(2) or "").upper()
                if suffix == "K":
                    number *= 1000
                elif suffix == "M":
                    number *= 1_000_000
                return int(number)

    return _as_int(
        _first_present(
            payload,
            [
                "boughtPastMonth",
                "bought_past_month",
                "monthlySold",
                "monthly_sold",
            ],
        )
    )


def _extract_image(payload: dict[str, Any]) -> str | None:
    for key in ("main_image", "mainImage", "image", "imageUrl"):
        image = payload.get(key)
        if isinstance(image, str):
            return image
        if isinstance(image, dict):
            url = image.get("link") or image.get("url")
            if url:
                return str(url)
    images = payload.get("images")
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            return first.get("link") or first.get("url")
    return None


def _extract_price(payload: dict[str, Any]) -> tuple[float | None, str | None]:
    buybox = payload.get("buybox_winner")
    if isinstance(buybox, dict):
        price = _as_float(
            _first_present(buybox, ["price", "price_value", "value", "current_price"])
        )
        currency = _first_present(buybox, ["currency", "currency_symbol"])
        if isinstance(currency, dict):
            currency = currency.get("code") or currency.get("symbol")
        if price is not None:
            return price, str(currency) if currency else "GBP"

    price = _as_float(
        _first_present(payload, ["price", "priceValue", "currentPrice", "buyBoxPrice"])
    )
    currency = _first_present(payload, ["currency", "currencyCode"])
    if isinstance(currency, dict):
        currency = currency.get("code") or currency.get("symbol")
    return price, str(currency) if currency else ("GBP" if price is not None else None)


def parse_detail_payload(asin: str, body: dict[str, Any]) -> EnrichedProduct:
    product = _unwrap_product(body)
    price, currency = _extract_price(product)

    rating = _as_float(_first_present(product, ["rating", "stars", "averageRating"]))
    if rating is None and isinstance(product.get("rating"), dict):
        rating = _as_float(product["rating"].get("value") or product["rating"].get("rating"))

    review_count = _as_int(
        _first_present(
            product,
            ["reviews_total", "reviewCount", "reviewsCount", "ratingsTotal", "reviews"],
        )
    )
    if review_count is None and isinstance(product.get("rating"), dict):
        review_count = _as_int(product["rating"].get("count") or product["rating"].get("total"))

    title = _first_present(product, ["title", "name", "productTitle"])
    brand = _first_present(product, ["brand", "brandName"])
    product_url = _first_present(product, ["url", "link", "productUrl"])
    if not product_url:
        product_url = f"https://www.amazon.co.uk/dp/{asin}"

    info = body.get("request_info") if isinstance(body.get("request_info"), dict) else {}
    credit_used = (
        _as_int(
            _first_present(
                info,
                ["credit_used_this_request", "credit_used", "credits_used_this_request"],
            )
        )
        or _as_int(
            _first_present(
                body,
                ["credit_used_this_request", "credit_used", "credits_used_this_request"],
            )
        )
        or 1
    )
    credits_remaining = _as_int(
        _first_present(info, ["credits_remaining", "credit_remaining"])
    ) or _as_int(_first_present(body, ["credits_remaining", "credit_remaining"]))

    return EnrichedProduct(
        asin=asin,
        title=str(title) if title else None,
        image_url=_extract_image(product),
        brand=str(brand) if brand else None,
        product_url=str(product_url) if product_url else None,
        price=price,
        currency=currency or "GBP",
        bsr=_extract_bsr(product),
        rating=rating,
        review_count=review_count,
        monthly_sold=_extract_monthly_sold(product),
        raw=body,
        credit_used=credit_used,
        credits_remaining=credits_remaining,
    )


def _search_candidate_items(body: dict[str, Any]) -> list[Any]:
    result = body.get("result")
    if isinstance(result, dict):
        for key in (
            "products",
            "results",
            "items",
            "searchResults",
            "organic_results",
            "search_results",
        ):
            value = result.get(key)
            if isinstance(value, list):
                return value
    if isinstance(result, list):
        return result
    return []


def _asin_from_search_item(item: Any) -> str | None:
    if isinstance(item, str):
        match = ASIN_RE.search(item)
        return match.group(1) if match else None
    if not isinstance(item, dict):
        return None
    raw = item.get("asin") or item.get("ASIN")
    if isinstance(raw, str) and re.fullmatch(r"[A-Z0-9]{10}", raw.upper()):
        return raw.upper()
    for field in ("url", "link", "productUrl", "product_url"):
        value = item.get(field)
        if isinstance(value, str):
            match = DP_RE.search(value)
            if match:
                return match.group(1).upper()
    return None


def _extract_asins_from_search(body: dict[str, Any], *, top_n: int) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for item in _search_candidate_items(body):
        asin = _asin_from_search_item(item)
        if asin and asin not in seen:
            seen.add(asin)
            ordered.append(asin)
        if len(ordered) >= top_n:
            return ordered

    for match in DP_RE.finditer(json.dumps(body, default=str)):
        asin = match.group(1).upper()
        if asin not in seen:
            seen.add(asin)
            ordered.append(asin)
        if len(ordered) >= top_n:
            break
    return ordered[:top_n]


def parse_search_hits(body: dict[str, Any], *, top_n: int) -> list[SearchHit]:
    """Parse organic SEARCH results into rich hits (ASIN + listing fields when present)."""
    hits: list[SearchHit] = []
    seen: set[str] = set()
    for item in _search_candidate_items(body):
        asin = _asin_from_search_item(item)
        if not asin or asin in seen:
            continue
        seen.add(asin)
        if isinstance(item, dict):
            price, currency = _extract_price(item)
            rating = _as_float(_first_present(item, ["rating", "stars", "averageRating"]))
            if rating is None and isinstance(item.get("rating"), dict):
                rating = _as_float(
                    item["rating"].get("value") or item["rating"].get("rating")
                )
            review_count = _as_int(
                _first_present(
                    item,
                    [
                        "reviews_total",
                        "reviewCount",
                        "reviewsCount",
                        "ratingsTotal",
                        "reviews",
                    ],
                )
            )
            title = _first_present(item, ["title", "name", "productTitle"])
            brand = _first_present(item, ["brand", "brandName"])
            product_url = _first_present(item, ["url", "link", "productUrl"])
            if not product_url:
                product_url = f"https://www.amazon.co.uk/dp/{asin}"
            hits.append(
                SearchHit(
                    position=len(hits) + 1,
                    asin=asin,
                    title=str(title) if title else None,
                    image_url=_extract_image(item),
                    brand=str(brand) if brand else None,
                    product_url=str(product_url) if product_url else None,
                    price=price,
                    currency=currency or ("GBP" if price is not None else None),
                    rating=rating,
                    review_count=review_count,
                    monthly_sold=_extract_monthly_sold(item),
                )
            )
        else:
            hits.append(
                SearchHit(
                    position=len(hits) + 1,
                    asin=asin,
                    product_url=f"https://www.amazon.co.uk/dp/{asin}",
                )
            )
        if len(hits) >= top_n:
            return hits

    # Fallback: ASIN-only scrape from raw JSON if structured list was empty/sparse.
    if not hits:
        for index, asin in enumerate(
            _extract_asins_from_search(body, top_n=top_n), start=1
        ):
            hits.append(
                SearchHit(
                    position=index,
                    asin=asin,
                    product_url=f"https://www.amazon.co.uk/dp/{asin}",
                )
            )
    return hits[:top_n]


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

    def _require_key(self) -> None:
        if not self.settings.easyparser_api_key.strip():
            raise RuntimeError(
                "EASYPARSER_API_KEY is empty. Save it in the project root .env and restart."
            )

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        self._require_key()
        last_error: Exception | None = None
        # Easyparser can be flaky from cloud IPs; retry briefly.
        for attempt in range(3):
            try:
                with httpx.Client(timeout=90.0) as client:
                    response = client.get(self.settings.easyparser_base_url, params=params)
                    try:
                        body = response.json()
                    except Exception as exc:  # noqa: BLE001
                        raise EasyparserRequestError(
                            f"Easyparser returned non-JSON (HTTP {response.status_code})"
                        ) from exc

                info = (
                    body.get("request_info")
                    if isinstance(body.get("request_info"), dict)
                    else {}
                )
                success = info.get("success")
                details = info.get("error_details") or []
                top_error = body.get("error")

                if response.status_code >= 400 or top_error or success is False:
                    if isinstance(details, list) and details:
                        message = (
                            details[0].get("message")
                            if isinstance(details[0], dict)
                            else details[0]
                        )
                    else:
                        message = top_error or f"HTTP {response.status_code}"
                    raise EasyparserRequestError(f"Easyparser error: {message}")
                return body
            except EasyparserRequestError as exc:
                last_error = exc
                if attempt < 2:
                    import time

                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        raise last_error or EasyparserRequestError("Easyparser request failed")


    def _track_credits(self, body: dict[str, Any], default_used: int = 1) -> int:
        info = body.get("request_info") if isinstance(body.get("request_info"), dict) else {}
        used = (
            _as_int(
                _first_present(
                    info,
                    ["credit_used_this_request", "credit_used", "credits_used_this_request"],
                )
            )
            or default_used
        )
        remaining = _as_int(
            _first_present(info, ["credits_remaining", "credit_remaining"])
        )
        self.credits_used_this_month += used
        if remaining is not None:
            self.last_credits_remaining = remaining
        return used

    def _search_request(
        self,
        *,
        keyword: str | None = None,
        url: str | None = None,
    ) -> tuple[dict[str, Any], int]:
        self.ensure_budget(1)
        params: dict[str, Any] = {
            "api_key": self.settings.easyparser_api_key,
            "platform": "AMZ",
            "operation": "SEARCH",
            "domain": self.settings.amazon_domain,
            "output": "json",
        }
        if url:
            params["url"] = url
        if keyword:
            params["keyword"] = keyword
        body = self._request(params)
        credit_used = self._track_credits(body, default_used=1)
        return body, credit_used

    def search_products(
        self,
        *,
        keyword: str | None = None,
        url: str | None = None,
        top_n: int = 10,
    ) -> tuple[list[BestsellerEntry], int]:
        body, credit_used = self._search_request(keyword=keyword, url=url)
        asins = _extract_asins_from_search(body, top_n=top_n)
        entries = [
            BestsellerEntry(rank=index, asin=asin)
            for index, asin in enumerate(asins, start=1)
        ]
        return entries, credit_used

    def search_catalog(
        self,
        *,
        keyword: str,
        top_n: int = 5,
    ) -> tuple[list[SearchHit], int]:
        """SEARCH for hunt MVP — 1 credit, up to top_n rich listing hits."""
        body, credit_used = self._search_request(keyword=keyword)
        return parse_search_hits(body, top_n=top_n), credit_used

    def get_bestsellers_rank(self, asin: str) -> tuple[int | None, int]:
        """Fetch BSR via BEST_SELLERS_RANK (1 credit). Returns (rank, credits_used)."""
        self.ensure_budget(1)
        body = self._request(
            {
                "api_key": self.settings.easyparser_api_key,
                "platform": "AMZ",
                "operation": "BEST_SELLERS_RANK",
                "domain": self.settings.amazon_domain,
                "asin": asin,
                "output": "json",
            }
        )
        used = self._track_credits(body, default_used=1)
        return parse_bestsellers_rank_payload(body), used

    def get_detail(self, asin: str) -> EnrichedProduct:
        self.ensure_budget(1)
        body = self._request(
            {
                "api_key": self.settings.easyparser_api_key,
                "platform": "AMZ",
                "operation": "DETAIL",
                "domain": self.settings.amazon_domain,
                "asin": asin,
                "output": "json",
            }
        )
        enriched = parse_detail_payload(asin, body)
        used = self._track_credits(body, default_used=enriched.credit_used or 1)

        # DETAIL often omits UK BSR; fill from dedicated operation when needed.
        if enriched.bsr is None and self.remaining_budget() >= 1:
            try:
                rank, rank_used = self.get_bestsellers_rank(asin)
                used += rank_used
                if rank is not None:
                    enriched.bsr = rank
            except EasyparserRequestError:
                pass

        enriched.credit_used = used
        if self.last_credits_remaining is not None:
            enriched.credits_remaining = self.last_credits_remaining
        return enriched
