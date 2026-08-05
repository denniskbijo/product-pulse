import { clearSession, loadSession, type Role } from "@/lib/auth";

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
  notes: string | null;
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

function formatApiError(text: string, status: number): string {
  try {
    const data = JSON.parse(text) as {
      detail?: string | { message?: string };
      message?: string;
    };
    if (typeof data.detail === "string") return data.detail;
    if (data.detail && typeof data.detail === "object" && data.detail.message) {
      return data.detail.message;
    }
    if (data.message) return data.message;
  } catch {
    // fall through
  }
  return text || `Request failed: ${status}`;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const session = loadSession();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (session?.accessToken) {
    headers.Authorization = `Bearer ${session.accessToken}`;
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (response.status === 401 && !path.startsWith("/auth/login")) {
    clearSession();
    if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
      window.location.href = "/login";
    }
  }

  if (!response.ok) {
    const text = await response.text();
    throw new Error(formatApiError(text, response.status));
  }
  return response.json() as Promise<T>;
}

export type LoginResult = {
  access_token: string;
  token_type: string;
  username: string;
  role: Role;
};

export function login(username: string, password: string) {
  return apiFetch<LoginResult>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export function getMe() {
  return apiFetch<{ username: string; role: Role }>("/auth/me");
}

export function getCategories() {
  return apiFetch<Category[]>("/categories");
}

export function getCategoryTop(idOrSlug: string | number) {
  return apiFetch<CategoryTop>(`/categories/${idOrSlug}/top?window=7d`);
}

export type SyncResult = {
  status: string;
  message: string;
  week_start: string;
  products_synced: number;
  credits_used: number;
  credits_remaining_budget: number | null;
};

export function triggerSync(idOrSlug: string | number, topN?: number) {
  const query = topN != null ? `?top_n=${topN}` : "";
  return apiFetch<SyncResult>(`/categories/${idOrSlug}/sync${query}`, {
    method: "POST",
  });
}

export type WatchlistProductAddResult = {
  status: "success" | "budget_exceeded" | "failed" | string;
  message: string;
  asin: string | null;
  title: string | null;
  rank: number | null;
  credits_used: number;
  credits_remaining_budget: number | null;
  week_start: string | null;
};

export function addWatchlistProduct(input: string) {
  return apiFetch<WatchlistProductAddResult>("/categories/watchlist/products", {
    method: "POST",
    body: JSON.stringify({ input }),
  });
}

export type PriceHistoryPoint = {
  date: string;
  price: number;
  currency: string | null;
  source: string;
};

export type ProductDetail = {
  asin: string;
  title: string | null;
  image_url: string | null;
  brand: string | null;
  product_url: string | null;
  notes: string | null;
  price: number | null;
  currency: string | null;
  price_change_absolute: number | null;
  price_change_percent: number | null;
  price_history_ready: boolean;
  estimated_weekly_units: number | null;
  sales_estimate_source: string | null;
  bsr: number | null;
  rating: number | null;
  review_count: number | null;
  monthly_sold: number | null;
  latest_week_start: string | null;
  updated_at: string | null;
  categories: Array<{
    slug: string;
    name: string;
    rank: number;
    week_start: string;
  }>;
  price_history: PriceHistoryPoint[];
};

export function getProductDetail(asin: string) {
  return apiFetch<ProductDetail>(`/products/${encodeURIComponent(asin)}`);
}

export type ProductNotesResult = {
  asin: string;
  notes: string | null;
};

export function updateProductNotes(asin: string, notes: string | null) {
  return apiFetch<ProductNotesResult>(`/products/${encodeURIComponent(asin)}`, {
    method: "PATCH",
    body: JSON.stringify({ notes }),
  });
}

export type ProductRemoveResult = {
  status: string;
  message: string;
  asin: string;
  category_id: number;
  snapshots_removed: number;
};

export function removeProductFromCategory(
  categoryIdOrSlug: string | number,
  asin: string,
) {
  return apiFetch<ProductRemoveResult>(
    `/categories/${categoryIdOrSlug}/products/${encodeURIComponent(asin)}`,
    { method: "DELETE" },
  );
}

export type HuntProductType = {
  slug: string;
  name: string;
  description: string;
};

export type HuntSeason = {
  slug: string;
  name: string;
  blurb: string;
  product_types: HuntProductType[];
};

export type HuntResult = {
  search_position: number;
  asin: string;
  title: string | null;
  image_url: string | null;
  brand: string | null;
  product_url: string | null;
  price: number | null;
  currency: string | null;
  rating: number | null;
  review_count: number | null;
  monthly_sold: number | null;
};

export type HuntRunSummary = {
  id: number;
  season_slug: string;
  product_type_slug: string;
  product_type_name: string;
  search_keyword: string;
  top_n: number;
  status: string;
  credits_used: number;
  result_count: number;
  error_message: string | null;
  created_by: string | null;
  started_at: string | null;
  finished_at: string | null;
};

export type HuntRunDetail = HuntRunSummary & {
  disclaimer: string;
  results: HuntResult[];
  credits_remaining_budget: number | null;
};

export function getHuntSeasons() {
  return apiFetch<HuntSeason[]>("/hunt/seasons");
}

export function listHuntRuns() {
  return apiFetch<HuntRunSummary[]>("/hunt/runs");
}

export function getHuntRun(runId: number) {
  return apiFetch<HuntRunDetail>(`/hunt/runs/${runId}`);
}

export function createHuntRun(seasonSlug: string, productTypeSlug: string) {
  return apiFetch<HuntRunDetail>("/hunt/runs", {
    method: "POST",
    body: JSON.stringify({
      season_slug: seasonSlug,
      product_type_slug: productTypeSlug,
    }),
  });
}
