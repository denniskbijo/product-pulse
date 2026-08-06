from app.providers.discovery.oxylabs import (
    parse_bestsellers_hits,
    parse_sales_volume,
    parse_search_hits,
)


def test_parse_sales_volume_variants():
    assert parse_sales_volume("200+ bought in past month") == 200
    assert parse_sales_volume("5K+ bought in past month") == 5000
    assert parse_sales_volume("1.2M purchased") == 1_200_000
    assert parse_sales_volume(None) is None


def test_parse_search_hits_organic_only():
    payload = {
        "results": [
            {
                "status_code": 200,
                "content": {
                    "results": {
                        "paid": [
                            {
                                "asin": "B0PAID0001",
                                "title": "Sponsored",
                                "pos": 1,
                                "sales_volume": "999+ bought in past month",
                            }
                        ],
                        "organic": [
                            {
                                "pos": 1,
                                "asin": "B0ORG00001",
                                "title": "Organic A",
                                "url": "/dp/B0ORG00001",
                                "url_image": "https://img/a.jpg",
                                "price": 19.99,
                                "currency": "GBP",
                                "rating": 4.5,
                                "reviews_count": 120,
                                "sales_volume": "1K+ bought in past month",
                                "manufacturer": "BrandA",
                            },
                            {
                                "pos": 2,
                                "asin": "B0ORG00002",
                                "title": "Organic B",
                                "url": "/dp/B0ORG00002",
                                "price": 9.5,
                                "currency": "GBP",
                                "sales_volume": "50+ bought in past month",
                            },
                        ],
                    }
                },
            }
        ]
    }
    hits = parse_search_hits(payload, top_n=5, marketplace_host="www.amazon.co.uk")
    assert len(hits) == 2
    assert hits[0].asin == "B0ORG00001"
    assert hits[0].monthly_sold == 1000
    assert hits[0].product_url.startswith("https://www.amazon.co.uk/")
    assert hits[1].asin == "B0ORG00002"


def test_parse_bestsellers_hits():
    payload = {
        "results": [
            {
                "status_code": 200,
                "content": {
                    "results": [
                        {
                            "pos": 1,
                            "asin": "B0BS000001",
                            "title": "Best seller",
                            "url": "/dp/B0BS000001",
                            "price": 12.0,
                            "currency": "GBP",
                            "rating": 4.8,
                            "ratings_count": 900,
                        }
                    ]
                },
            }
        ]
    }
    hits = parse_bestsellers_hits(
        payload, top_n=5, marketplace_host="www.amazon.co.uk"
    )
    assert len(hits) == 1
    assert hits[0].asin == "B0BS000001"
    assert hits[0].monthly_sold is None
