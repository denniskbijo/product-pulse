"""Fetch Amazon UK product prices from the mobile product page (no Easyparser)."""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)
PRICE_RE = re.compile(r"([0-9]+(?:\.[0-9]{1,2})?)")
BLOCK_MARKERS = (
    "robot check",
    "validatecaptcha",
    "api-services-support@amazon.com",
    "enter the characters you see below",
    "sorry, we just need to make sure you're not a robot",
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


def mobile_product_url(asin: str, *, host: str = "www.amazon.co.uk") -> str:
    return f"https://{host}/gp/aw/d/{asin}"


def is_blocked_html(html: str) -> bool:
    lower = html.lower()
    return any(marker in lower for marker in BLOCK_MARKERS)


def parse_mobile_product_html(html: str, *, asin: str) -> MobilePriceResult:
    if is_blocked_html(html):
        return MobilePriceResult(asin=asin, status="blocked", error="Amazon bot check page")

    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one("#productTitle, #title, span#title")
    title = title_el.get_text(strip=True) if title_el else None

    price: float | None = None
    currency: str | None = None
    for el in soup.select("span.a-price span.a-offscreen"):
        text = el.get_text(" ", strip=True)
        if not text:
            continue
        if "£" in text:
            currency = "GBP"
        elif "$" in text:
            currency = "USD"
        elif "€" in text:
            currency = "EUR"
        match = PRICE_RE.search(text.replace(",", ""))
        if match:
            price = float(match.group(1))
            break

    if price is None:
        return MobilePriceResult(
            asin=asin,
            status="parse_error",
            title=title,
            error="No price found in mobile HTML",
        )

    return MobilePriceResult(
        asin=asin,
        status="success",
        price=price,
        currency=currency or "GBP",
        title=title,
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
    )
