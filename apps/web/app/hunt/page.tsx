"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  addWatchlistProduct,
  createHuntRun,
  getHuntRun,
  getHuntSeasons,
  listHuntRuns,
  type HuntRunDetail,
  type HuntRunSummary,
  type HuntSeason,
} from "@/lib/api";
import { clearSession, isAdmin, loadSession, type Session } from "@/lib/auth";
import { formatMonthlySold } from "@/lib/labels";

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

export default function HuntPage() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [seasons, setSeasons] = useState<HuntSeason[]>([]);
  const [seasonSlug, setSeasonSlug] = useState("winter");
  const [typeSlug, setTypeSlug] = useState("");
  const [runs, setRuns] = useState<HuntRunSummary[]>([]);
  const [activeRun, setActiveRun] = useState<HuntRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [addingAsin, setAddingAsin] = useState<string | null>(null);

  const admin = isAdmin(session);
  const season = useMemo(
    () => seasons.find((s) => s.slug === seasonSlug) || null,
    [seasons, seasonSlug],
  );
  const productTypes = season?.product_types || [];

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
    Promise.all([getHuntSeasons(), listHuntRuns()])
      .then(([seasonList, runList]) => {
        setSeasons(seasonList);
        setRuns(runList);
        const winter = seasonList.find((s) => s.slug === "winter") || seasonList[0];
        if (winter) {
          setSeasonSlug(winter.slug);
          setTypeSlug(winter.product_types[0]?.slug || "");
        }
        if (runList[0]) {
          return getHuntRun(runList[0].id).then(setActiveRun);
        }
        return null;
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load hunt");
      });
  }, [ready, session?.accessToken]);

  const onRun = async () => {
    if (!admin || !typeSlug) return;
    setRunning(true);
    setError(null);
    setMessage(null);
    try {
      const detail = await createHuntRun(seasonSlug, typeSlug);
      setActiveRun(detail);
      setRuns((prev) => [
        {
          id: detail.id,
          season_slug: detail.season_slug,
          product_type_slug: detail.product_type_slug,
          product_type_name: detail.product_type_name,
          search_keyword: detail.search_keyword,
          top_n: detail.top_n,
          status: detail.status,
          credits_used: detail.credits_used,
          result_count: detail.result_count,
          error_message: detail.error_message,
          created_by: detail.created_by,
          started_at: detail.started_at,
          finished_at: detail.finished_at,
        },
        ...prev.filter((r) => r.id !== detail.id),
      ]);
      if (detail.status === "success") {
        setMessage(
          `Found ${detail.result_count} candidate${detail.result_count === 1 ? "" : "s"} · ${detail.credits_used} credit used`,
        );
      } else {
        setError(detail.error_message || detail.status);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Hunt failed");
    } finally {
      setRunning(false);
    }
  };

  const onOpenRun = async (runId: number) => {
    setError(null);
    try {
      setActiveRun(await getHuntRun(runId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load hunt run");
    }
  };

  const onAddWatchlist = async (asin: string) => {
    setAddingAsin(asin);
    setError(null);
    setMessage(null);
    try {
      const result = await addWatchlistProduct(asin);
      if (result.status === "success") {
        setMessage(result.message);
      } else {
        setError(result.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add to watchlist");
    } finally {
      setAddingAsin(null);
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
          <h1 className="brand">Winter Hunt</h1>
          <div className="session-bar">
            <a className="text-link" href="/">
              ← Dashboard
            </a>
            <span className="note">{session.username}</span>
            <button
              className="button secondary compact"
              onClick={() => {
                clearSession();
                router.replace("/login");
              }}
            >
              Log out
            </button>
          </div>
        </div>
        <p className="lede">
          Start with a season, pick a product type, then find five live UK
          candidates. This shows current Amazon demand — not last December’s
          bestsellers archive.
        </p>
      </section>

      <section className="status">
        <div className="controls">
          <div className="field">
            <label htmlFor="season">Season</label>
            <select
              id="season"
              value={seasonSlug}
              onChange={(e) => {
                const next = e.target.value;
                setSeasonSlug(next);
                const match = seasons.find((s) => s.slug === next);
                setTypeSlug(match?.product_types[0]?.slug || "");
              }}
            >
              {seasons.map((s) => (
                <option key={s.slug} value={s.slug}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div className="field field-watchlist">
            <label htmlFor="product-type">Product type</label>
            <select
              id="product-type"
              value={typeSlug}
              onChange={(e) => setTypeSlug(e.target.value)}
            >
              {productTypes.map((pt) => (
                <option key={pt.slug} value={pt.slug}>
                  {pt.name}
                </option>
              ))}
            </select>
          </div>
          {admin ? (
            <button
              className="button"
              disabled={running || !typeSlug}
              onClick={() => void onRun()}
            >
              {running ? "Searching…" : "Run hunt (1 credit)"}
            </button>
          ) : (
            <p className="note">Only admins can run hunts. You can browse recent results.</p>
          )}
        </div>
        {season ? <p className="note">{season.blurb}</p> : null}
        {productTypes.find((p) => p.slug === typeSlug)?.description ? (
          <p className="note">
            {productTypes.find((p) => p.slug === typeSlug)?.description}
          </p>
        ) : null}
        {admin && activeRun?.credits_remaining_budget != null ? (
          <p className="note">
            Enrichment credits left this month:{" "}
            <strong>{activeRun.credits_remaining_budget}</strong>
          </p>
        ) : null}
        {message ? <p className="note">{message}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </section>

      {runs.length > 0 ? (
        <section className="detail-panel" style={{ marginBottom: "1.25rem" }}>
          <h2>Recent hunts</h2>
          <div className="product-actions">
            {runs.slice(0, 8).map((run) => (
              <button
                key={run.id}
                type="button"
                className={
                  activeRun?.id === run.id
                    ? "button compact"
                    : "button secondary compact"
                }
                onClick={() => void onOpenRun(run.id)}
              >
                {run.product_type_name}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <section className="products-section">
        {!activeRun ? (
          <div className="empty">
            {admin
              ? "Pick a product type and run a hunt to see five candidates."
              : "No hunt results yet."}
          </div>
        ) : (
          <>
            <div className="status" style={{ marginBottom: "1rem" }}>
              <div>
                <strong>{activeRun.product_type_name}</strong> ·{" "}
                {activeRun.search_keyword} · {activeRun.status}
              </div>
              <p className="note">{activeRun.disclaimer}</p>
            </div>

            <ul className="hunt-results">
              {activeRun.results.map((product) => (
                <li key={product.asin} className="product-card">
                  <div className="product-card-top">
                    <span className="product-rank">#{product.search_position}</span>
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
                  </div>
                  <dl className="product-metrics">
                    <div>
                      <dt>Price</dt>
                      <dd>{formatPrice(product.price, product.currency)}</dd>
                    </div>
                    <div>
                      <dt>Bought past month</dt>
                      <dd>{formatMonthlySold(product.monthly_sold)}</dd>
                    </div>
                    <div>
                      <dt>Rating</dt>
                      <dd>
                        {product.rating != null ? product.rating.toFixed(1) : "—"}
                        {product.review_count != null
                          ? ` · ${product.review_count.toLocaleString("en-GB")}`
                          : ""}
                      </dd>
                    </div>
                  </dl>
                  <div className="product-actions">
                    <button
                      type="button"
                      className="button secondary compact"
                      disabled={addingAsin === product.asin}
                      onClick={() => void onAddWatchlist(product.asin)}
                    >
                      {addingAsin === product.asin
                        ? "Adding…"
                        : "Add to Watchlist"}
                    </button>
                  </div>
                </li>
              ))}
            </ul>

            {activeRun.results.length === 0 ? (
              <div className="empty">No products returned for this hunt.</div>
            ) : null}
          </>
        )}
      </section>

      <p className="footer">
        Each hunt uses 1 Easyparser SEARCH credit and returns up to five
        candidates. Adding to Watchlist uses a separate DETAIL credit for full
        enrichment. Historical winter validation (Keepa) is not part of this MVP.
      </p>
    </main>
  );
}
