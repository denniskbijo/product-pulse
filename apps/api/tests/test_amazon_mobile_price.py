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

# Mirrors the Rinsemate bidet page: sponsored carousel before the real buybox.
SAMPLE_SPONSORED_BEFORE_BUYBOX = """
<html><body>
  <span id="productTitle">Rinsemate Portable Bidet</span>
  <div id="sp_ilm_phone_shared_row2" class="sp_ilm_phone_shared_row2">
    <span class="a-price"><span class="a-offscreen">£50.99</span></span>
  </div>
  <div id="corePriceDisplay_mobile_feature_div">
    <span class="a-price aok-align-center reinventPricePriceToPayMargin">
      <span class="a-offscreen"></span>
    </span>
  </div>
  <div id="tp_price_block_total_price_ww">
    <span class="a-price"><span class="a-offscreen">£48.99</span></span>
  </div>
  <div id="sp_phone_detail_B0OTHER">
    <span class="a-price apex-price-to-pay-value">
      <span class="a-offscreen">£43.99</span>
    </span>
  </div>
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


def test_parse_mobile_prefers_buybox_over_sponsored_carousel():
    result = parse_mobile_product_html(SAMPLE_SPONSORED_BEFORE_BUYBOX, asin="B0GV4558G7")
    assert result.status == "success"
    assert result.price == 48.99
    assert result.currency == "GBP"
