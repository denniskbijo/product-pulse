from app.providers.enrichment.easyparser import parse_search_hits


def test_parse_search_hits_extracts_listing_fields():
    body = {
        "result": {
            "products": [
                {
                    "asin": "B0TESTAAAA",
                    "title": "Cosy Electric Blanket",
                    "brand": "WarmCo",
                    "buybox_winner": {"price": 29.99, "currency": "GBP"},
                    "rating": 4.4,
                    "reviews_total": 1200,
                    "bought_activity": {
                        "period": "past month",
                        "raw": "2K+ bought",
                        "value": 2000,
                    },
                    "main_image": {"link": "https://example.com/a.jpg"},
                    "url": "https://www.amazon.co.uk/dp/B0TESTAAAA",
                },
                {
                    "asin": "B0TESTBBBB",
                    "title": "Budget Blanket",
                    "link": "https://www.amazon.co.uk/dp/B0TESTBBBB",
                },
            ]
        }
    }
    hits = parse_search_hits(body, top_n=5)
    assert len(hits) == 2
    assert hits[0].asin == "B0TESTAAAA"
    assert hits[0].monthly_sold == 2000
    assert hits[0].price == 29.99
    assert hits[1].asin == "B0TESTBBBB"
    assert hits[1].monthly_sold is None


def test_parse_search_hits_respects_top_n():
    body = {
        "result": {
            "organic_results": [
                {"asin": f"B0TEST{i:04d}", "title": f"Item {i}"} for i in range(10)
            ]
        }
    }
    hits = parse_search_hits(body, top_n=5)
    assert len(hits) == 5
    assert hits[0].position == 1
    assert hits[4].position == 5
