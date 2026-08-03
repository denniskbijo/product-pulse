from app.providers.prices.amazon_mobile import parse_mobile_product_html

SAMPLE_OK = """
<html><body>
  <span id="productTitle">Test Kettle</span>
  <span class="a-price"><span class="a-offscreen">£24.99</span></span>
  <span class="a-price"><span class="a-offscreen">£29.99</span></span>
</body></html>
"""

SAMPLE_BLOCKED = """
<html><body>
  <h1>Robot Check</h1>
  <p>Enter the characters you see below</p>
  <form action="/errors/validateCaptcha"></form>
</body></html>
"""

SAMPLE_NO_PRICE = """
<html><body>
  <span id="productTitle">Mystery Item</span>
</body></html>
"""


def test_parse_mobile_extracts_first_gbp_price():
    result = parse_mobile_product_html(SAMPLE_OK, asin="B0TESTASIN")
    assert result.status == "success"
    assert result.price == 24.99
    assert result.currency == "GBP"
    assert result.title == "Test Kettle"


def test_parse_mobile_detects_bot_wall():
    result = parse_mobile_product_html(SAMPLE_BLOCKED, asin="B0TESTASIN")
    assert result.status == "blocked"
    assert result.price is None


def test_parse_mobile_missing_price():
    result = parse_mobile_product_html(SAMPLE_NO_PRICE, asin="B0TESTASIN")
    assert result.status == "parse_error"
    assert result.title == "Mystery Item"
