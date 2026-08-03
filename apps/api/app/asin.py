from __future__ import annotations

import re

_DP_RE = re.compile(r"/dp/([A-Z0-9]{10})", re.IGNORECASE)
_GP_PRODUCT_RE = re.compile(r"/gp/product/([A-Z0-9]{10})", re.IGNORECASE)
_PLAIN_ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")


def parse_asin_from_input(raw: str) -> str:
    """Extract a 10-character ASIN from plain text or an Amazon product URL."""
    text = raw.strip()
    if not text:
        raise ValueError("input is required")

    for pattern in (_DP_RE, _GP_PRODUCT_RE):
        match = pattern.search(text)
        if match:
            return match.group(1).upper()

    candidate = text.upper()
    if _PLAIN_ASIN_RE.fullmatch(candidate):
        return candidate

    raise ValueError(
        "Invalid ASIN or Amazon product URL. Provide a 10-character ASIN or a "
        "URL containing /dp/ASIN or /gp/product/ASIN."
    )
