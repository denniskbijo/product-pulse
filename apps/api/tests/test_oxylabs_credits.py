from app.providers.discovery.oxylabs import parse_monthly_results_used


def test_parse_monthly_results_used():
    payload = {
        "data": [
            {
                "date": "2026-08",
                "products": [
                    {"title": "serp_scraper_api", "all_count": 0},
                    {"title": "ecommerce_scraper_api", "all_count": 2},
                    {"title": "web_scraper_api", "all_count": 0},
                ],
            }
        ]
    }
    assert parse_monthly_results_used(payload, month_key="2026-08") == 2
    assert parse_monthly_results_used(payload, month_key="2026-07") == 0
