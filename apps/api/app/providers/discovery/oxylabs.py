"""Oxylabs Web Scraper API client for Winter Hunt (Amazon UK search / bestsellers)."""

from __future__ import annotations

import re
from typing import Any, Literal

import httpx

from app.config import Settings
from app.providers.enrichment.easyparser import SearchHit

ASIN_RE = re.compile(r"\b([A-Z0-9]{10})\b")
DP_RE = re.compile(r"/dp/([A-Z0-9]{10})")
SALES_VOLUME_RE = re.compile(
    r"([\d,.]+)\s*([KkMm])?\+?\s*(?:bought|purchased)?",
    re.IGNORECASE,
)


class OxylabsRequestError(RuntimeError):
    pass


def oxylabs_configured(settings: Settings) -> bool:
    return bool(settings.oxylabs_username.strip() and settings.oxylabs_password.strip())


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
    return None


def parse_sales_volume(raw: Any) -> int | None:
    """Parse Oxylabs sales_volume strings like '200+ bought in past month'."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return int(raw)
    if not isinstance(raw, str):
        return None
    match = SALES_VOLUME_RE.search(raw)
    if not match:
        return _as_int(raw)
    number = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").upper()
    if suffix == "K":
        number *= 1000
    elif suffix == "M":
        number *= 1_000_000
    return int(number)


def _extract_asin(item: dict[str, Any]) -> str | None:
    asin = item.get("asin")
    if isinstance(asin, str) and ASIN_RE.fullmatch(asin.upper()):
        return asin.upper()
    url = item.get("url") or item.get("product_url") or ""
    if isinstance(url, str):
        match = DP_RE.search(url) or ASIN_RE.search(url)
        if match:
            return match.group(1).upper()
    return None


def _absolute_product_url(url: str | None, asin: str, marketplace_host: str) -> str:
    if url and url.startswith("http"):
        return url
    if url and url.startswith("/"):
        return f"https://{marketplace_host}{url.split('?', 1)[0]}"
    return f"https://{marketplace_host}/dp/{asin}"


def parse_search_hits(
    payload: dict[str, Any],
    *,
    top_n: int,
    marketplace_host: str,
) -> list[SearchHit]:
    """Parse amazon_search realtime payload into SearchHit rows (organic only)."""
    content = _first_content(payload)
    results = content.get("results")
    organic: list[Any] = []
    if isinstance(results, dict):
        organic = results.get("organic") or []
    elif isinstance(results, list):
        organic = results

    hits: list[SearchHit] = []
    seen: set[str] = set()
    for index, item in enumerate(organic, start=1):
        if not isinstance(item, dict):
            continue
        asin = _extract_asin(item)
        if not asin or asin in seen:
            continue
        seen.add(asin)
        position = _as_int(item.get("pos")) or index
        url = item.get("url")
        url_str = str(url) if isinstance(url, str) else None
        hits.append(
            SearchHit(
                position=position,
                asin=asin,
                title=str(item["title"]) if item.get("title") else None,
                image_url=(
                    str(item["url_image"])
                    if isinstance(item.get("url_image"), str)
                    else None
                ),
                brand=(
                    str(item["manufacturer"])
                    if item.get("manufacturer")
                    else None
                ),
                product_url=_absolute_product_url(url_str, asin, marketplace_host),
                price=_as_float(item.get("price")),
                currency=str(item["currency"]) if item.get("currency") else "GBP",
                rating=_as_float(item.get("rating")),
                review_count=_as_int(
                    item.get("reviews_count") or item.get("ratings_count")
                ),
                monthly_sold=parse_sales_volume(item.get("sales_volume")),
            )
        )
        if len(hits) >= top_n:
            break
    return hits


def parse_bestsellers_hits(
    payload: dict[str, Any],
    *,
    top_n: int,
    marketplace_host: str,
) -> list[SearchHit]:
    """Parse amazon_bestsellers realtime payload into SearchHit rows."""
    content = _first_content(payload)
    results = content.get("results")
    rows: list[Any]
    if isinstance(results, list):
        rows = results
    elif isinstance(results, dict):
        rows = results.get("organic") or results.get("paid") or []
    else:
        rows = []

    hits: list[SearchHit] = []
    seen: set[str] = set()
    for index, item in enumerate(rows, start=1):
        if not isinstance(item, dict):
            continue
        asin = _extract_asin(item)
        if not asin or asin in seen:
            continue
        seen.add(asin)
        position = _as_int(item.get("pos")) or index
        url = item.get("url")
        url_str = str(url) if isinstance(url, str) else None
        hits.append(
            SearchHit(
                position=position,
                asin=asin,
                title=str(item["title"]) if item.get("title") else None,
                image_url=(
                    str(item["url_image"])
                    if isinstance(item.get("url_image"), str)
                    else None
                ),
                brand=None,
                product_url=_absolute_product_url(url_str, asin, marketplace_host),
                price=_as_float(item.get("price") or item.get("price_str")),
                currency=str(item["currency"]) if item.get("currency") else "GBP",
                rating=_as_float(item.get("rating")),
                review_count=_as_int(
                    item.get("ratings_count") or item.get("reviews_count")
                ),
                monthly_sold=None,
            )
        )
        if len(hits) >= top_n:
            break
    return hits


def _first_content(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results")
    if isinstance(results, list) and results:
        first = results[0]
        if isinstance(first, dict):
            content = first.get("content")
            if isinstance(content, dict):
                return content
            if isinstance(content, str):
                raise OxylabsRequestError(
                    "Oxylabs returned HTML without parse=true structured content."
                )
    if isinstance(payload.get("content"), dict):
        return payload["content"]
    return payload if isinstance(payload, dict) else {}


def parse_monthly_results_used(stats_payload: dict[str, Any], *, month_key: str) -> int | None:
    """
    Sum result counts for the given YYYY-MM from Oxylabs /v2/stats?group_by=month.
    Returns None if the month cannot be found / payload is unexpected.
    """
    data = stats_payload.get("data")
    rows: list[Any]
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        # Ungrouped shape: treat as total only when month matches "all".
        products = data.get("products")
        if isinstance(products, list):
            return sum(int(p.get("all_count") or 0) for p in products if isinstance(p, dict))
        return None
    else:
        return None

    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("date") or "") != month_key:
            continue
        products = row.get("products")
        if not isinstance(products, list):
            return 0
        total = 0
        for product in products:
            if isinstance(product, dict):
                total += int(product.get("all_count") or 0)
        return total
    return 0


class OxylabsClient:
    def __init__(self, settings: Settings, *, timeout: float = 120.0) -> None:
        self.settings = settings
        self.timeout = timeout
        self.username = settings.oxylabs_username.strip()
        self.password = settings.oxylabs_password.strip()
        self.base_url = settings.oxylabs_base_url.rstrip("/")
        self.stats_url = settings.oxylabs_stats_url.rstrip("/")
        self.domain = settings.oxylabs_amazon_domain.strip() or "co.uk"
        self.marketplace_host = settings.amazon_marketplace_host.strip() or "www.amazon.co.uk"

    def fetch_month_results_used(self, *, month_key: str) -> int | None:
        """Return results used this month from Oxylabs stats, or None if unavailable."""
        if not self.username or not self.password:
            return None
        try:
            response = httpx.get(
                self.stats_url,
                params={"group_by": "month"},
                auth=(self.username, self.password),
                timeout=min(self.timeout, 30.0),
            )
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        if not isinstance(payload, dict):
            return None
        return parse_monthly_results_used(payload, month_key=month_key)

    def hunt_catalog(
        self,
        *,
        keyword: str,
        top_n: int = 5,
        browse_node: str | None = None,
    ) -> tuple[list[SearchHit], int, Literal["amazon_search", "amazon_bestsellers"]]:
        """
        One Oxylabs request per hunt.
        Prefer amazon_bestsellers when a browse node is configured; else amazon_search.
        Returns (hits, requests_used, source).
        """
        if not self.username or not self.password:
            raise OxylabsRequestError(
                "Oxylabs credentials are not configured "
                "(set OXYLABS_USERNAME and OXYLABS_PASSWORD)."
            )

        node = (browse_node or "").strip()
        if node:
            payload = self._query(
                {
                    "source": "amazon_bestsellers",
                    "domain": self.domain,
                    "query": node,
                    "parse": True,
                    "start_page": 1,
                    "pages": 1,
                    "context": [{"key": "currency", "value": "GBP"}],
                }
            )
            hits = parse_bestsellers_hits(
                payload, top_n=top_n, marketplace_host=self.marketplace_host
            )
            return hits, 1, "amazon_bestsellers"

        payload = self._query(
            {
                "source": "amazon_search",
                "domain": self.domain,
                "query": keyword,
                "parse": True,
                "start_page": 1,
                "pages": 1,
                "locale": "en_GB",
                "context": [{"key": "currency", "value": "GBP"}],
            }
        )
        hits = parse_search_hits(
            payload, top_n=top_n, marketplace_host=self.marketplace_host
        )
        return hits, 1, "amazon_search"

    def _query(self, body: dict[str, Any]) -> dict[str, Any]:
        try:
            response = httpx.post(
                self.base_url,
                json=body,
                auth=(self.username, self.password),
                headers={"Content-Type": "application/json"},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise OxylabsRequestError(f"Oxylabs request failed: {exc}") from exc

        if response.status_code == 401:
            raise OxylabsRequestError("Oxylabs authentication failed (check username/password).")
        if response.status_code >= 400:
            detail = response.text[:400]
            raise OxylabsRequestError(
                f"Oxylabs HTTP {response.status_code}: {detail or 'request failed'}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise OxylabsRequestError("Oxylabs returned non-JSON response.") from exc

        if not isinstance(data, dict):
            raise OxylabsRequestError("Unexpected Oxylabs response shape.")

        results = data.get("results")
        if isinstance(results, list) and results:
            first = results[0]
            if isinstance(first, dict):
                status_code = first.get("status_code")
                if status_code not in (None, 200):
                    raise OxylabsRequestError(
                        f"Oxylabs scrape status_code={status_code}"
                    )
        return data
