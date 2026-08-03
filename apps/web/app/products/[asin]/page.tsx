"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { getProductDetail, type ProductDetail } from "@/lib/api";
import { clearSession, loadSession } from "@/lib/auth";

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

function PriceSparkline({
  points,
}: {
  points: Array<{ date: string; price: number }>;
}) {
  const path = useMemo(() => {
    if (points.length < 2) return null;
    const prices = points.map((p) => p.price);
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const span = max - min || 1;
    const w = 320;
    const h = 96;
    const pad = 8;
    const coords = points.map((point, index) => {
      const x = pad + (index / (points.length - 1)) * (w - pad * 2);
      const y = pad + (1 - (point.price - min) / span) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return { d: `M ${coords.join(" L ")}`, w, h, min, max };
  }, [points]);

  if (!path) {
    return <p className="note">Need at least two price points for a chart.</p>;
  }

  return (
    <div className="sparkline-wrap">
      <svg
        className="sparkline"
        viewBox={`0 0 ${path.w} ${path.h}`}
        role="img"
        aria-label="Price history sparkline"
      >
        <path d={path.d} fill="none" stroke="currentColor" strokeWidth="2.5" />
      </svg>
      <div className="sparkline-scale">
        <span>{formatPrice(path.max, "GBP")}</span>
        <span>{formatPrice(path.min, "GBP")}</span>
      </div>
    </div>
  );
}

export default function ProductDetailPage() {
  const params = useParams<{ asin: string }>();
  const router = useRouter();
  const asin = decodeURIComponent(params.asin || "").toUpperCase();
  const [detail, setDetail] = useState<ProductDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const session = loadSession();
    if (!session) {
      router.replace("/login");
      return;
    }
    if (!asin) {
      setError("Missing ASIN");
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    getProductDetail(asin)
      .then((data) => {
        if (!cancelled) {
          setDetail(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setDetail(null);
          setError(err instanceof Error ? err.message : "Failed to load product");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [asin, router]);

  const delta = formatDelta(
    detail?.price_change_absolute ?? null,
    detail?.price_change_percent ?? null,
  );

  return (
    <main className="shell detail-shell">
      <header className="detail-nav">
        <a className="text-link" href="/">
          ← Back to dashboard
        </a>
        <button
          className="button secondary compact"
          onClick={() => {
            clearSession();
            router.replace("/login");
          }}
        >
          Log out
        </button>
      </header>

      {loading ? <p className="note">Loading product…</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {detail ? (
        <>
          <section className="detail-hero">
            <div className="detail-media">
              {detail.image_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={detail.image_url} alt="" className="detail-image" />
              ) : (
                <div className="detail-image placeholder" />
              )}
            </div>
            <div className="detail-summary">
              <p className="asin">{detail.asin}</p>
              <h1 className="detail-title">{detail.title || detail.asin}</h1>
              {detail.brand ? <p className="note">Brand: {detail.brand}</p> : null}
              <div className="detail-price-row">
                <div>
                  <span className="metric-label">Current price</span>
                  <strong className="detail-price">
                    {formatPrice(detail.price, detail.currency)}
                  </strong>
                </div>
                <div>
                  <span className="metric-label">7-day Δ</span>
                  <strong className={delta.className}>{delta.text}</strong>
                </div>
              </div>
              <div className="detail-actions">
                <a
                  className="button"
                  href={
                    detail.product_url ||
                    `https://www.amazon.co.uk/dp/${detail.asin}`
                  }
                  target="_blank"
                  rel="noreferrer"
                >
                  View on Amazon UK
                </a>
              </div>
            </div>
          </section>

          <section className="detail-panel">
            <h2>Stored enrichment</h2>
            <p className="note">
              From Easyparser weekly/featured sync — viewing this page does not
              use credits.
            </p>
            <dl className="detail-grid">
              <div>
                <dt>Best Sellers Rank</dt>
                <dd>
                  {detail.bsr != null
                    ? detail.bsr.toLocaleString("en-GB")
                    : "—"}
                </dd>
              </div>
              <div>
                <dt>Est. weekly units</dt>
                <dd>
                  {detail.estimated_weekly_units != null
                    ? `~${detail.estimated_weekly_units}`
                    : "—"}
                  {detail.sales_estimate_source ? (
                    <span className="asin">{detail.sales_estimate_source}</span>
                  ) : null}
                </dd>
              </div>
              <div>
                <dt>Monthly sold</dt>
                <dd>
                  {detail.monthly_sold != null
                    ? detail.monthly_sold.toLocaleString("en-GB")
                    : "—"}
                </dd>
              </div>
              <div>
                <dt>Rating</dt>
                <dd>
                  {detail.rating != null ? detail.rating.toFixed(1) : "—"}
                  {detail.review_count != null
                    ? ` · ${detail.review_count.toLocaleString("en-GB")} reviews`
                    : ""}
                </dd>
              </div>
              <div>
                <dt>Latest week start</dt>
                <dd>{detail.latest_week_start || "—"}</dd>
              </div>
              <div>
                <dt>Categories</dt>
                <dd>
                  {detail.categories.length
                    ? detail.categories
                        .map((c) => `${c.name} (#${c.rank})`)
                        .join(", ")
                    : "—"}
                </dd>
              </div>
            </dl>
          </section>

          <section className="detail-panel">
            <h2>7-day price monitoring</h2>
            <p className="note">
              Daily Amazon mobile scrapes when available; weekly snapshots fill
              gaps.
            </p>
            <PriceSparkline points={detail.price_history} />
            {detail.price_history.length === 0 ? (
              <p className="note">
                No price history yet. Run a sync or `make scrape-prices`.
              </p>
            ) : (
              <div className="table-wrap detail-history">
                <table className="product-table">
                  <thead>
                    <tr>
                      <th>Date</th>
                      <th>Price</th>
                      <th>Source</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...detail.price_history].reverse().map((point) => (
                      <tr key={`${point.date}-${point.source}`}>
                        <td>{point.date}</td>
                        <td>{formatPrice(point.price, point.currency)}</td>
                        <td>{point.source}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </main>
  );
}
