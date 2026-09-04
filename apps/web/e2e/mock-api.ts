import type { Page } from "@playwright/test";

export const API_ORIGIN = "http://127.0.0.1:4010";

export const SESSION = {
  accessToken: "test-token",
  username: "basil",
  role: "user" as const,
};

const sync = {
  last_sync_at: null,
  last_status: null,
  last_week_start: null,
  last_products_synced: null,
  last_error: null,
  credits: {
    monthly_budget: 100,
    credits_used: 0,
    credits_remaining_budget: 100,
    credits_remaining_reported: null,
    month_key: "2026-09",
  },
};

export const watchlistProduct = {
  rank: 1,
  asin: "B09RKS585V",
  title: "Ilex Wood Deodorant",
  image_url: null,
  brand: "The Ilex Wood",
  product_url: "https://www.amazon.co.uk/dp/B09RKS585V",
  notes: null,
  price: 8.45,
  currency: "GBP",
  price_change_absolute: null,
  price_change_percent: null,
  estimated_weekly_units: null,
  sales_estimate_source: null,
  bsr: 1200,
  rating: 4.1,
  review_count: 6103,
  reviews_added: 4,
  reviews_added_7d: 12,
  review_momentum: "rising",
  monthly_sold: 1000,
};

export function watchlistTop() {
  return {
    category: {
      id: 1,
      slug: "watchlist",
      name: "Watchlist",
      bestsellers_url: "https://www.amazon.co.uk/",
    },
    window: "7d",
    week_start: "2026-09-01",
    as_of: null,
    price_history_ready: true,
    note: null,
    products: [watchlistProduct],
    sync,
  };
}

export function productDetail(historyEnd?: string | null) {
  const recent = !historyEnd || historyEnd >= "2026-09-04";
  return {
    asin: "B09RKS585V",
    title: "Ilex Wood Deodorant",
    image_url: null,
    brand: "The Ilex Wood",
    product_url: "https://www.amazon.co.uk/dp/B09RKS585V",
    notes: null,
    price: 8.45,
    currency: "GBP",
    price_change_absolute: 0.2,
    price_change_percent: 2.4,
    price_history_ready: true,
    estimated_weekly_units: null,
    sales_estimate_source: null,
    bsr: 1200,
    rating: 4.1,
    review_count: 6103,
    reviews_added: 4,
    reviews_added_7d: 12,
    review_momentum: "rising",
    monthly_sold: 1000,
    latest_week_start: "2026-09-01",
    updated_at: null,
    categories: [
      { slug: "watchlist", name: "Watchlist", rank: 1, week_start: "2026-09-01" },
    ],
    history_days: 7,
    history_start: recent ? "2026-08-29" : "2026-08-22",
    history_end: recent ? "2026-09-04" : "2026-08-28",
    history_has_older: recent,
    history_has_newer: !recent,
    price_history: recent
      ? [
          { date: "2026-09-01", price: 8.25, currency: "GBP", source: "amazon_mobile" },
          { date: "2026-09-04", price: 8.45, currency: "GBP", source: "amazon_mobile" },
        ]
      : [
          { date: "2026-08-22", price: 7.99, currency: "GBP", source: "amazon_mobile" },
          { date: "2026-08-28", price: 8.1, currency: "GBP", source: "amazon_mobile" },
        ],
    review_history: recent
      ? [
          {
            date: "2026-09-01",
            review_count: 6099,
            reviews_added: 2,
            rating: 4.1,
            source: "amazon_mobile",
          },
          {
            date: "2026-09-04",
            review_count: 6103,
            reviews_added: 4,
            rating: 4.1,
            source: "amazon_mobile",
          },
        ]
      : [
          {
            date: "2026-08-22",
            review_count: 6080,
            reviews_added: 1,
            rating: 4.1,
            source: "amazon_mobile",
          },
          {
            date: "2026-08-28",
            review_count: 6090,
            reviews_added: 3,
            rating: 4.1,
            source: "amazon_mobile",
          },
        ],
  };
}

export async function seedSession(page: Page) {
  await page.addInitScript((session) => {
    localStorage.setItem("product-pulse-session", JSON.stringify(session));
  }, SESSION);
}

export async function mockPulseApi(page: Page) {
  await page.route(`${API_ORIGIN}/**`, async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();

    if (method === "OPTIONS") {
      await route.fulfill({ status: 204 });
      return;
    }

    if (path === "/auth/login" && method === "POST") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          access_token: SESSION.accessToken,
          token_type: "bearer",
          username: SESSION.username,
          role: SESSION.role,
        }),
      });
      return;
    }

    if (path === "/auth/me") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({ username: SESSION.username, role: SESSION.role }),
      });
      return;
    }

    if (path === "/categories") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: 1,
            slug: "watchlist",
            name: "Watchlist",
            bestsellers_url: "https://www.amazon.co.uk/",
          },
        ]),
      });
      return;
    }

    if (path === "/categories/watchlist/top") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(watchlistTop()),
      });
      return;
    }

    if (path === "/products/B09RKS585V" && method === "GET") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify(productDetail(url.searchParams.get("history_end"))),
      });
      return;
    }

    await route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ detail: `Unhandled mock ${method} ${path}` }),
    });
  });
}
