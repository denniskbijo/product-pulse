from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})")
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class BestsellerEntry:
    rank: int
    asin: str


def parse_bestsellers_html(html: str, *, top_n: int = 10) -> list[BestsellerEntry]:
    """Extract ranked ASINs from an Amazon Best Sellers page."""
    soup = BeautifulSoup(html, "lxml")
    ordered: list[str] = []
    seen: set[str] = set()

    # Prefer grid/list item cards Amazon uses on bestseller pages.
    cards = soup.select(
        "div#gridItemRoot, div.zg-grid-general-faceout, "
        "div.p13n-sc-uncoverable-faceout, li.zg-item-immersion, "
        "div[data-asin]"
    )
    for card in cards:
        asin = (card.get("data-asin") or "").strip()
        if not asin:
            link = card.select_one('a[href*="/dp/"]')
            if link and link.get("href"):
                match = ASIN_RE.search(link["href"])
                asin = match.group(1) if match else ""
        if asin and asin not in seen and re.fullmatch(r"[A-Z0-9]{10}", asin):
            seen.add(asin)
            ordered.append(asin)
        if len(ordered) >= top_n:
            break

    # Fallback: scan all /dp/ links in document order.
    if len(ordered) < top_n:
        for link in soup.select('a[href*="/dp/"]'):
            href = link.get("href") or ""
            match = ASIN_RE.search(href)
            if not match:
                continue
            asin = match.group(1)
            if asin in seen:
                continue
            seen.add(asin)
            ordered.append(asin)
            if len(ordered) >= top_n:
                break

    return [
        BestsellerEntry(rank=index, asin=asin)
        for index, asin in enumerate(ordered[:top_n], start=1)
    ]


def fetch_bestsellers(
    url: str,
    *,
    top_n: int = 10,
    timeout: float = 30.0,
) -> list[BestsellerEntry]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml",
    }
    with httpx.Client(follow_redirects=True, timeout=timeout, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        return parse_bestsellers_html(response.text, top_n=top_n)
