"""Fetch Amazon UK product prices from the mobile product page (no Easyparser)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup, Tag

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)
PRICE_RE = re.compile(r"([0-9]+(?:\.[0-9]{1,2})?)")
RATING_RE = re.compile(r"(\d(?:\.\d)?)\s+out of\s+5", re.I)
REVIEW_COUNT_RE = re.compile(
    r"([\d,]+)\s+(?:global\s+)?(?:ratings?|reviews?)",
    re.I,
)
PAREN_COUNT_RE = re.compile(r"\(([\d,]+)\)")
BLOCK_MARKERS = (
    "robot check",
    "validatecaptcha",
    "api-services-support@amazon.com",
    "enter the characters you see below",
    "sorry, we just need to make sure you're not a robot",
)

# Prefer the product buybox over sponsored / related carousels that also use a-price.
BUYBOX_SELECTORS = (
    "#tp_price_block_total_price_ww span.a-offscreen",
    "#corePriceDisplay_mobile_feature_div span.a-price.aok-align-center span.a-offscreen",
    "#corePriceDisplay_mobile_feature_div span.a-offscreen",
    "#corePrice_feature_div span.a-offscreen",
    "#apex_offerDisplay_desktop span.a-offscreen",
    "span.priceToPay span.a-offscreen",
    ".a-price.reinventPricePriceToPayMargin span.a-offscreen",
)

SPONSORED_MARKERS = (
    "sp_ilm",
    "sp_phone",
    "sp_detail",
    "AdHolder",
    "sponsored",
    "puis-sponsored",
)


@dataclass(frozen=True)
class MobilePriceResult:
    asin: str
    status: str  # success | blocked | not_found | parse_error | http_error
    price: float | None = None
    currency: str | None = None
    title: str | None = None
    error: str | None = None
    http_status: int | None = None
    review_count: int | None = None
    rating: float | None = None


def mobile_product_url(asin: str, *, host: str = "www.amazon.co.uk") -> str:
    return f"https://{host}/gp/aw/d/{asin}"


def is_blocked_html(html: str) -> bool:
    lower = html.lower()
    return any(marker in lower for marker in BLOCK_MARKERS)


def _parse_price_text(text: str) -> tuple[float | None, str | None]:
    cleaned = text.strip()
    if not cleaned or cleaned.lower() == "null":
        return None, None
    currency: str | None = None
    if "£" in cleaned or "GBP" in cleaned.upper():
        currency = "GBP"
    elif "$" in cleaned or "USD" in cleaned.upper():
        currency = "USD"
    elif "€" in cleaned or "EUR" in cleaned.upper():
        currency = "EUR"
    match = PRICE_RE.search(cleaned.replace(",", ""))
    if not match:
        return None, currency
    return float(match.group(1)), currency


def _is_sponsored_context(el: Tag) -> bool:
    for parent in el.parents:
        if not isinstance(parent, Tag):
            continue
        pid = parent.get("id") or ""
        classes = " ".join(parent.get("class") or [])
        blob = f"{pid} {classes}"
        if any(marker in blob for marker in SPONSORED_MARKERS):
            return True
    return False


def _parse_int_count(raw: str) -> int | None:
    digits = raw.replace(",", "").strip()
    if not digits.isdigit():
        return None
    return int(digits)


def parse_mobile_reviews(soup: BeautifulSoup) -> tuple[int | None, float | None]:
    """Read lifetime ratings/reviews from the product ACR block (not related items)."""
    review_count: int | None = None
    rating: float | None = None

    acr = soup.select_one(
        "#acrCustomerReviewLink, #acrCustomerReviewText, #averageCustomerReviews"
    )
    acr_text = acr.get_text(" ", strip=True) if acr else ""
    if acr_text:
        rating_match = RATING_RE.search(acr_text)
        if rating_match:
            rating = float(rating_match.group(1))
        paren = PAREN_COUNT_RE.search(acr_text)
        if paren:
            review_count = _parse_int_count(paren.group(1))
        if review_count is None:
            count_match = REVIEW_COUNT_RE.search(acr_text)
            if count_match:
                review_count = _parse_int_count(count_match.group(1))

    if review_count is None:
        block = soup.select_one("#averageCustomerReviews_feature_div")
        block_text = block.get_text(" ", strip=True) if block else ""
        count_match = REVIEW_COUNT_RE.search(block_text)
        if count_match:
            review_count = _parse_int_count(count_match.group(1))
        if rating is None:
            rating_match = RATING_RE.search(block_text)
            if rating_match:
                rating = float(rating_match.group(1))

    return review_count, rating


def parse_mobile_product_html(html: str, *, asin: str) -> MobilePriceResult:
    if is_blocked_html(html):
        return MobilePriceResult(asin=asin, status="blocked", error="Amazon bot check page")

    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one("#productTitle, #title, span#title")
    title = title_el.get_text(strip=True) if title_el else None
    review_count, rating = parse_mobile_reviews(soup)

    price: float | None = None
    currency: str | None = None

    # 1) Explicit buybox containers first.
    for selector in BUYBOX_SELECTORS:
        for el in soup.select(selector):
            parsed_price, parsed_currency = _parse_price_text(el.get_text(" ", strip=True))
            if parsed_price is None:
                continue
            price = parsed_price
            currency = parsed_currency
            break
        if price is not None:
            break

    # 2) Fallback: first non-sponsored a-price offscreen.
    if price is None:
        for el in soup.select("span.a-price span.a-offscreen"):
            if _is_sponsored_context(el):
                continue
            parsed_price, parsed_currency = _parse_price_text(el.get_text(" ", strip=True))
            if parsed_price is None:
                continue
            price = parsed_price
            currency = parsed_currency
            break

    if price is None:
        return MobilePriceResult(
            asin=asin,
            status="parse_error",
            title=title,
            error="No price found in mobile HTML",
            review_count=review_count,
            rating=rating,
        )

    return MobilePriceResult(
        asin=asin,
        status="success",
        price=price,
        currency=currency or "GBP",
        title=title,
        review_count=review_count,
        rating=rating,
    )


def fetch_mobile_price(
    asin: str,
    *,
    host: str = "www.amazon.co.uk",
    timeout: float = 30.0,
) -> MobilePriceResult:
    headers = {
        "User-Agent": MOBILE_UA,
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }
    url = mobile_product_url(asin, host=host)
    try:
        with httpx.Client(headers=headers, follow_redirects=True, timeout=timeout) as client:
            response = client.get(url)
    except httpx.HTTPError as exc:
        return MobilePriceResult(asin=asin, status="http_error", error=str(exc))

    if response.status_code == 404:
        return MobilePriceResult(
            asin=asin,
            status="not_found",
            http_status=404,
            error="Product page not found",
        )
    if response.status_code >= 400:
        return MobilePriceResult(
            asin=asin,
            status="http_error",
            http_status=response.status_code,
            error=f"HTTP {response.status_code}",
        )

    parsed = parse_mobile_product_html(response.text, asin=asin)
    return MobilePriceResult(
        asin=parsed.asin,
        status=parsed.status,
        price=parsed.price,
        currency=parsed.currency,
        title=parsed.title,
        error=parsed.error,
        http_status=response.status_code,
        review_count=parsed.review_count,
        rating=parsed.rating,
    )
