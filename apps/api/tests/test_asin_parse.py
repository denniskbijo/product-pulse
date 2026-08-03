import pytest

from app.asin import parse_asin_from_input


def test_parse_plain_asin():
    assert parse_asin_from_input("B0ABCDEF12") == "B0ABCDEF12"
    assert parse_asin_from_input("  b0abcdef12  ") == "B0ABCDEF12"


def test_parse_dp_url():
    url = "https://www.amazon.co.uk/Some-Product/dp/B0ABCDEF12/ref=sr_1_1"
    assert parse_asin_from_input(url) == "B0ABCDEF12"


def test_parse_gp_product_url():
    url = "https://www.amazon.co.uk/gp/product/B0ABCDEF12"
    assert parse_asin_from_input(url) == "B0ABCDEF12"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "B0SHORT",
        "not-an-asin",
        "https://www.amazon.co.uk/s?k=kettle",
    ],
)
def test_parse_rejects_invalid_input(raw: str):
    with pytest.raises(ValueError):
        parse_asin_from_input(raw)
