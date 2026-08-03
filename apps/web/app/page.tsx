"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  addFeaturedProduct,
  Category,
  CategoryTop,
  getCategories,
  getCategoryTop,
  TopProduct,
  triggerSync,
} from "@/lib/api";
import { clearSession, isAdmin, loadSession, type Session } from "@/lib/auth";

function formatPrice(price: number | null, currency: string | null) {
  if (price == null) return "—";
  try {
    return new Intl.NumberFormat("en-GB", {
      style: "currency",
      currency: currency || "GBP",
    }).format(price);
  } catch {
    return `£${price.toFixed(2)}`;
  }
}

function formatDelta(absolute: number | null, percent: number | null) {
  if (absolute == null) return { text: "Collecting…", className: "flat" };
  const sign = absolute > 0 ? "+" : "";
  const pct = percent == null ? "" : ` (${sign}${percent.toFixed(1)}%)`;
  const className = absolute > 0 ? "up" : absolute < 0 ? "down" : "flat";
  return {
    text: `${sign}${absolute.toFixed(2)}${pct}`,
    className,
  };
}

function formatWhen(value: string | null) {
  if (!value) return "Never";
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function productHref(product: TopProduct) {
  return product.product_url || `https://www.amazon.co.uk/dp/${product.asin}`;
}

function ProductIdentity({ product }: { product: TopProduct }) {
  return (
    <div className="product">
      {product.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          className="thumb"
          src={product.image_url}
          alt=""
          width={56}
          height={56}
        />
      ) : (
        <div className="thumb" />
      )}
      <div className="product-copy">
        <a href={productHref(product)} target="_blank" rel="noreferrer">
          {product.title || product.asin}
        </a>
        <span className="asin">{product.asin}</span>
      </div>
    </div>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selected, setSelected] = useState<string>("home-kitchen");
  const [data, setData] = useState<CategoryTop | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [syncing, setSyncing] = useState<"full" | "one" | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [featuredInput, setFeaturedInput] = useState("");
  const [addingFeatured, setAddingFeatured] = useState(false);
  const [featuredAddMessage, setFeaturedAddMessage] = useState<string | null>(
    null,
  );
  const [featuredAddError, setFeaturedAddError] = useState<string | null>(null);

  const admin = isAdmin(session);
  const hasProducts = (data?.products.length ?? 0) > 0;

  const load = (slug: string) => {
    startTransition(async () => {
      setError(null);
      try {
        const top = await getCategoryTop(slug);
        setData(top);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load category");
      }
    });
  };

  useEffect(() => {
    const current = loadSession();
    if (!current) {
      router.replace("/login");
      return;
    }
    setSession(current);
    setReady(true);
  }, [router]);

  useEffect(() => {
    if (!ready || !session) return;
    getCategories()
      .then((cats) => {
        setCategories(cats);
        const initial =
          cats.find((c) => c.slug === "home-kitchen")?.slug || cats[0]?.slug;
        if (initial) {
          setSelected(initial);
          load(initial);
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load categories");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready, session?.accessToken]);

  const credits = data?.sync.credits;
  const creditLabel = useMemo(() => {
    if (!credits || !admin) return null;
    return `${credits.credits_remaining_budget} / ${credits.monthly_budget} budget left (${credits.month_key})`;
  }, [credits, admin]);

  const onSync = async (topN?: number) => {
    if (!admin) return;
    setSyncing(topN === 1 ? "one" : "full");
    setError(null);
    setSyncMessage(null);
    try {
      const result = await triggerSync(selected, topN);
      setSyncMessage(result.message);
      if (result.status !== "success") {
        setError(result.message);
      }
      await load(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(null);
    }
  };

  const onLogout = () => {
    clearSession();
    router.replace("/login");
  };

  const onAddFeatured = async () => {
    const input = featuredInput.trim();
    if (!input) return;
    setAddingFeatured(true);
    setFeaturedAddMessage(null);
    setFeaturedAddError(null);
    try {
      const result = await addFeaturedProduct(input);
      if (result.status === "success") {
        setFeaturedAddMessage(result.message);
        setFeaturedInput("");
        if (selected !== "featured") {
          setSelected("featured");
        }
        load("featured");
      } else if (result.status === "budget_exceeded" && !admin) {
        setFeaturedAddError(
          "Monthly enrichment limit reached. Contact an admin.",
        );
      } else {
        setFeaturedAddError(result.message);
      }
    } catch (err) {
      setFeaturedAddError(
        err instanceof Error ? err.message : "Failed to add product",
      );
    } finally {
      setAddingFeatured(false);
    }
  };

  if (!ready || !session) {
    return (
      <main className="shell">
        <p className="note">Checking session…</p>
      </main>
    );
  }

  return (
    <main className="shell">
      <section className="hero">
        <div className="hero-top">
          <h1 className="brand">Amazon Pulse</h1>
          <div className="session-bar">
            <span className="note">
              {session.username} · {session.role}
            </span>
            <button className="button secondary compact" onClick={onLogout}>
              Log out
            </button>
          </div>
        </div>
        <p className="lede">
          UK category top sellers — current price, estimated weekly volume, and
          7-day price changes.
        </p>
        <div className="controls">
          <div className="field">
            <label htmlFor="category">Category</label>
            <select
              id="category"
              value={selected}
              onChange={(event) => {
                const slug = event.target.value;
                setSelected(slug);
                load(slug);
              }}
            >
              {categories.map((category) => (
                <option key={category.slug} value={category.slug}>
                  {category.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field field-featured">
            <label htmlFor="featured-input">Featured ASIN or URL</label>
            <input
              id="featured-input"
              type="text"
              placeholder="B0… or amazon.co.uk/dp/…"
              value={featuredInput}
              onChange={(event) => setFeaturedInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void onAddFeatured();
                }
              }}
              disabled={addingFeatured || pending}
            />
          </div>
          <button
            className="button secondary"
            onClick={() => void onAddFeatured()}
            disabled={addingFeatured || pending || !featuredInput.trim()}
          >
            {addingFeatured ? "Adding…" : "Add product"}
          </button>
          {admin ? (
            <>
              <button
                className={hasProducts ? "button secondary" : "button"}
                onClick={() => onSync(1)}
                disabled={syncing != null || pending}
                title="Enrich the #1 product for this category"
              >
                {syncing === "one" ? "Syncing…" : "Sync 1 product"}
              </button>
              <button
                className={hasProducts ? "button" : "button secondary"}
                onClick={() => onSync()}
                disabled={syncing != null || pending}
              >
                {syncing === "full" ? "Syncing…" : "Sync top 10"}
              </button>
            </>
          ) : null}
        </div>
        {featuredAddMessage ? (
          <p className="note">{featuredAddMessage}</p>
        ) : null}
        {featuredAddError ? (
          <p className="error">{featuredAddError}</p>
        ) : null}
      </section>

      {!hasProducts && admin ? (
        <section className="empty-cta">
          <h2>No products yet</h2>
          <p className="note">
            Run a sync to pull category data into the database. Cached results will
            show here for everyone after that.
          </p>
          <button
            className="button"
            onClick={() => onSync(1)}
            disabled={syncing != null || pending}
          >
            {syncing ? "Syncing…" : "Sync 1 product"}
          </button>
        </section>
      ) : null}

      <section className="status">
        <div>
          Last sync: <strong>{formatWhen(data?.sync.last_sync_at ?? null)}</strong>
          {data?.sync.last_status && admin ? ` · ${data.sync.last_status}` : ""}
        </div>
        {admin && creditLabel ? (
          <div>
            Easyparser credits: <strong>{creditLabel}</strong>
            {credits?.credits_remaining_reported != null
              ? ` · provider reports ${credits.credits_remaining_reported} remaining`
              : ""}
          </div>
        ) : null}
        {admin && syncMessage ? <p className="note">{syncMessage}</p> : null}
        {admin && data?.note ? <p className="note">{data.note}</p> : null}
        {admin && data?.sync.last_error ? (
          <p className="error">Last sync error: {data.sync.last_error}</p>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      <section className="products-section">
        {!data || data.products.length === 0 ? (
          <div className="empty">
            {pending ? "Loading…" : "No products in the database yet."}
          </div>
        ) : (
          <>
            <ul className="product-cards">
              {data.products.map((product) => {
                const delta = formatDelta(
                  product.price_change_absolute,
                  product.price_change_percent,
                );
                return (
                  <li key={product.asin} className="product-card">
                    <div className="product-card-top">
                      <span className="product-rank">#{product.rank}</span>
                      <ProductIdentity product={product} />
                    </div>
                    <dl className="product-metrics">
                      <div>
                        <dt>Price</dt>
                        <dd>{formatPrice(product.price, product.currency)}</dd>
                      </div>
                      <div>
                        <dt>7-day Δ</dt>
                        <dd className={delta.className}>{delta.text}</dd>
                      </div>
                      <div>
                        <dt>Est. weekly units</dt>
                        <dd>
                          {product.estimated_weekly_units != null
                            ? `~${product.estimated_weekly_units}`
                            : "—"}
                          {product.sales_estimate_source ? (
                            <span className="asin">
                              {product.sales_estimate_source}
                            </span>
                          ) : null}
                        </dd>
                      </div>
                      <div>
                        <dt>Best Sellers Rank</dt>
                        <dd>
                          {product.bsr != null
                            ? product.bsr.toLocaleString("en-GB")
                            : "—"}
                        </dd>
                      </div>
                    </dl>
                  </li>
                );
              })}
            </ul>

            <div className="table-wrap">
              <table className="product-table">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Product</th>
                    <th>Price</th>
                    <th>7-day Δ</th>
                    <th>Est. weekly units</th>
                    <th>Best Sellers Rank</th>
                  </tr>
                </thead>
                <tbody>
                  {data.products.map((product) => {
                    const delta = formatDelta(
                      product.price_change_absolute,
                      product.price_change_percent,
                    );
                    return (
                      <tr key={product.asin}>
                        <td>#{product.rank}</td>
                        <td>
                          <ProductIdentity product={product} />
                        </td>
                        <td>{formatPrice(product.price, product.currency)}</td>
                        <td className={delta.className}>{delta.text}</td>
                        <td>
                          {product.estimated_weekly_units != null
                            ? `~${product.estimated_weekly_units}`
                            : "—"}
                          {product.sales_estimate_source ? (
                            <span className="asin">
                              {product.sales_estimate_source}
                            </span>
                          ) : null}
                        </td>
                        <td>
                          {product.bsr != null
                            ? product.bsr.toLocaleString("en-GB")
                            : "—"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>

      <p className="footer">
        Sales units are estimates (Amazon “bought in past month” when available,
        otherwise a UK Best Sellers Rank curve). Rich fields come from weekly
        Easyparser sync; daily prices come from Amazon mobile pages
        (`make scrape-prices`, max 10). 7-day Δ prefers daily history when
        available.
      </p>
    </main>
  );
}
