const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type Category = {
  id: number;
  slug: string;
  name: string;
  bestsellers_url: string;
};

export type TopProduct = {
  rank: number;
  asin: string;
  title: string | null;
  image_url: string | null;
  brand: string | null;
  product_url: string | null;
  price: number | null;
  currency: string | null;
  price_change_absolute: number | null;
  price_change_percent: number | null;
  estimated_weekly_units: number | null;
  sales_estimate_source: string | null;
  bsr: number | null;
  rating: number | null;
  review_count: number | null;
  monthly_sold: number | null;
};

export type CategoryTop = {
  category: Category;
  window: string;
  week_start: string | null;
  as_of: string | null;
  price_history_ready: boolean;
  note: string | null;
  products: TopProduct[];
  sync: {
    last_sync_at: string | null;
    last_status: string | null;
    last_week_start: string | null;
    last_products_synced: number | null;
    last_error: string | null;
    credits: {
      monthly_budget: number;
      credits_used: number;
      credits_remaining_budget: number;
      credits_remaining_reported: number | null;
      month_key: string;
    };
  };
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getCategories() {
  return apiFetch<Category[]>("/categories");
}

export function getCategoryTop(idOrSlug: string | number) {
  return apiFetch<CategoryTop>(`/categories/${idOrSlug}/top?window=7d`);
}

export function triggerSync(idOrSlug: string | number) {
  return apiFetch<{
    status: string;
    message: string;
    week_start: string;
    products_synced: number;
    credits_used: number;
    credits_remaining_budget: number | null;
  }>(`/categories/${idOrSlug}/sync`, { method: "POST" });
}
