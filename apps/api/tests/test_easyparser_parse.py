from app.providers.enrichment.easyparser import EasyparserClient, parse_detail_payload
from app.config import Settings


def test_parse_detail_payload_extracts_core_fields():
    body = {
        "credit_used_this_request": 1,
        "credits_remaining": 99,
        "result": {
            "title": "Test Kettle",
            "brand": "BrandX",
            "price": "24.99",
            "currency": "GBP",
            "rating": 4.5,
            "reviewCount": "1,234",
            "boughtPastMonth": "2000",
            "bestsellers_rank": [{"category": "Kitchen", "rank": 12}],
            "image": "https://example.com/img.jpg",
            "url": "https://www.amazon.co.uk/dp/B0TESTASIN",
        },
    }
    product = parse_detail_payload("B0TESTASIN", body)
    assert product.title == "Test Kettle"
    assert product.price == 24.99
    assert product.monthly_sold == 2000
    assert product.bsr == 12
    assert product.review_count == 1234
    assert product.credits_remaining == 99


def test_credit_budget_guard():
    settings = Settings(
        easyparser_api_key="test",
        monthly_credit_budget=100,
    )
    client = EasyparserClient(settings, credits_used_this_month=99)
    assert client.remaining_budget() == 1
    client.ensure_budget(1)
    try:
        client.ensure_budget(2)
        raised = False
    except Exception:
        raised = True
    assert raised
