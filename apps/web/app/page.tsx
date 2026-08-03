"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import {
  Category,
  CategoryTop,
  getCategories,
  getCategoryTop,
  triggerSync,
} from "@/lib/api";

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

export default function HomePage() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [selected, setSelected] = useState<string>("home-kitchen");
  const [data, setData] = useState<CategoryTop | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [syncing, setSyncing] = useState(false);

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
    getCategories()
      .then((cats) => {
        setCategories(cats);
        const initial = cats.find((c) => c.slug === "home-kitchen")?.slug || cats[0]?.slug;
        if (initial) {
          setSelected(initial);
          load(initial);
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load categories");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const credits = data?.sync.credits;
  const creditLabel = useMemo(() => {
    if (!credits) return "—";
    return `${credits.credits_remaining_budget} / ${credits.monthly_budget} budget left (${credits.month_key})`;
  }, [credits]);

  const onSync = async () => {
    setSyncing(true);
    setError(null);
    try {
      await triggerSync(selected);
      await load(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  return (
    <main className="shell">
      <section className="hero">
        <h1 className="brand">Amazon Pulse</h1>
        <p className="lede">
          UK category top sellers — current price, estimated weekly volume, and
          week-over-week price changes. Discovery from Amazon Best Sellers pages;
          enrichment via Easyparser free credits.
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
          <button className="button" onClick={onSync} disabled={syncing || pending}>
            {syncing ? "Syncing…" : "Sync now"}
          </button>
        </div>
      </section>

      <section className="status">
        <div>
          Last sync: <strong>{formatWhen(data?.sync.last_sync_at ?? null)}</strong>
          {data?.sync.last_status ? ` · ${data.sync.last_status}` : ""}
        </div>
        <div>
          Easyparser credits: <strong>{creditLabel}</strong>
          {credits?.credits_remaining_reported != null
            ? ` · provider reports ${credits.credits_remaining_reported} remaining`
            : ""}
        </div>
        {data?.note ? <p className="note">{data.note}</p> : null}
        {data?.sync.last_error ? (
          <p className="error">Last sync error: {data.sync.last_error}</p>
        ) : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      <section className="table-wrap">
        {!data || data.products.length === 0 ? (
          <div className="empty">
            {pending
              ? "Loading…"
              : "No products yet. Click Sync now (requires EASYPARSER_API_KEY)."}
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Rank</th>
                <th>Product</th>
                <th>Price</th>
                <th>WoW Δ</th>
                <th>Est. weekly units</th>
                <th>BSR</th>
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
                        <div>
                          <a
                            href={
                              product.product_url ||
                              `https://www.amazon.co.uk/dp/${product.asin}`
                            }
                            target="_blank"
                            rel="noreferrer"
                          >
                            {product.title || product.asin}
                          </a>
                          <span className="asin">{product.asin}</span>
                        </div>
                      </div>
                    </td>
                    <td>{formatPrice(product.price, product.currency)}</td>
                    <td className={delta.className}>{delta.text}</td>
                    <td>
                      {product.estimated_weekly_units != null
                        ? `~${product.estimated_weekly_units}`
                        : "—"}
                      {product.sales_estimate_source ? (
                        <span className="asin">{product.sales_estimate_source}</span>
                      ) : null}
                    </td>
                    <td>{product.bsr != null ? product.bsr.toLocaleString("en-GB") : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      <p className="footer">
        Sales units are estimates (Amazon “bought in past month” when available,
        otherwise a UK BSR curve). Prices come from Easyparser market observations.
        Week-over-week price changes appear after the second weekly sync.
      </p>
    </main>
  );
}
