from app.config import Settings
from app.providers.enrichment.easyparser import (
    EasyparserClient,
    parse_bestsellers_rank_payload,
    parse_detail_payload,
)


def test_parse_detail_payload_nested_result_detail():
    body = {
        "request_info": {
            "success": True,
            "credit_used_this_request": 1,
            "credits_remaining": 97,
        },
        "result": {
            "detail": {
                "title": "Test Kettle",
                "brand": "BrandX",
                "buybox_winner": {"price": 24.99, "currency": "GBP"},
                "rating": 4.5,
                "reviews_total": 1234,
                "bought_activity": {"period": "past month", "raw": "700+ bought", "value": 700},
                "bestsellers_rank": [{"category": "Kitchen", "rank": 12}],
                "main_image": {"link": "https://example.com/img.jpg"},
                "url": "https://www.amazon.co.uk/dp/B0TESTASIN",
            }
        },
    }
    product = parse_detail_payload("B0TESTASIN", body)
    assert product.title == "Test Kettle"
    assert product.price == 24.99
    assert product.monthly_sold == 700
    assert product.bsr == 12
    assert product.review_count == 1234
    assert product.credits_remaining == 97
    assert product.image_url == "https://example.com/img.jpg"


def test_parse_bestsellers_rank_operation():
    body = {
        "request_info": {"success": True, "credit_used_this_request": 1},
        "result": {
            "country_code": "GB",
            "product": {
                "asin": "B09RKS585V",
                "bestseller": {
                    "context_name": "Handmade Products",
                    "rank": 3,
                    "sub_category_id": "51708350",
                },
            },
        },
    }
    assert parse_bestsellers_rank_payload(body) == 3


def test_extract_bsr_from_bestseller_object_on_detail():
    body = {
        "request_info": {"success": True},
        "result": {
            "detail": {
                "title": "Deodorant",
                "bestseller": {"rank": 42, "context_name": "Handmade"},
            }
        },
    }
    product = parse_detail_payload("B09RKS585V", body)
    assert product.bsr == 42


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
