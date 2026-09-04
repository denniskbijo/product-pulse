"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  HISTORY_TABLE_PAGE_SIZE,
  HISTORY_WINDOW_DAYS,
  getProductDetail,
  updateProductNotes,
  type ProductDetail,
} from "@/lib/api";
import { clearSession, loadSession } from "@/lib/auth";
import {
  formatBsr,
  formatMonthlySold,
  formatPriceChange,
  formatPriceHistorySource,
  formatReviewMomentum,
  formatReviewsAdded,
} from "@/lib/labels";

function todayIso(): string {
  const now = new Date();
  return [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, "0"),
    String(now.getDate()).padStart(2, "0"),
  ].join("-");
}

function addDaysIso(iso: string, days: number): string {
  const [year, month, day] = iso.split("-").map(Number);
  const next = new Date(year, month - 1, day + days);
  return [
    next.getFullYear(),
    String(next.getMonth() + 1).padStart(2, "0"),
    String(next.getDate()).padStart(2, "0"),
  ].join("-");
}

function formatIsoRange(start?: string | null, end?: string | null): string {
  if (!start || !end) return "Last 7 days";
  const fmt = (iso: string) => {
    const [year, month, day] = iso.split("-").map(Number);
    return new Date(year, month - 1, day).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
    });
  };
  return start === end ? fmt(start) : `${fmt(start)} – ${fmt(end)}`;
}

function pageSlice<T>(rows: T[], page: number, pageSize: number) {
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const safe = Math.min(Math.max(0, page), pages - 1);
  return {
    page: safe,
    pages,
    rows: rows.slice(safe * pageSize, (safe + 1) * pageSize),
  };
}

function HistoryRangePager({
  start,
  end,
  hasOlder,
  hasNewer,
  busy,
  onOlder,
  onNewer,
}: {
  start?: string | null;
  end?: string | null;
  hasOlder?: boolean;
  hasNewer?: boolean;
  busy: boolean;
  onOlder: () => void;
  onNewer: () => void;
}) {
  return (
    <div className="history-pager" data-testid="history-pager">
      <button
        type="button"
        className="button secondary compact"
        disabled={!hasOlder || busy}
        onClick={onOlder}
      >
        Older
      </button>
      <span className="note">{formatIsoRange(start, end)}</span>
      <button
        type="button"
        className="button secondary compact"
        disabled={!hasNewer || busy}
        onClick={onNewer}
      >
        Newer
      </button>
    </div>
  );
}

function TablePager({
  page,
  pages,
  busy,
  onChange,
}: {
  page: number;
  pages: number;
  busy?: boolean;
  onChange: (page: number) => void;
}) {
  if (pages <= 1) return null;
  return (
    <div className="table-pager">
      <button
        type="button"
        className="button secondary compact"
        disabled={page <= 0 || busy}
        onClick={() => onChange(page - 1)}
      >
        Previous
      </button>
      <span className="note">
        Page {page + 1} of {pages}
      </span>
      <button
        type="button"
        className="button secondary compact"
        disabled={page >= pages - 1 || busy}
        onClick={() => onChange(page + 1)}
      >
        Next
      </button>
    </div>
  );
}

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
        aria-label="Price history chart"
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

function ReviewSparkline({
  points,
}: {
  points: Array<{ date: string; review_count: number }>;
}) {
  const path = useMemo(() => {
    if (points.length < 2) return null;
    const counts = points.map((p) => p.review_count);
    const min = Math.min(...counts);
    const max = Math.max(...counts);
    const span = max - min || 1;
    const w = 320;
    const h = 96;
    const pad = 8;
    const coords = points.map((point, index) => {
      const x = pad + (index / (points.length - 1)) * (w - pad * 2);
      const y = pad + (1 - (point.review_count - min) / span) * (h - pad * 2);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    return { d: `M ${coords.join(" L ")}`, w, h, min, max };
  }, [points]);

  if (!path) {
    return (
      <p className="note">Need at least two daily review counts for a chart.</p>
    );
  }

  return (
    <div className="sparkline-wrap">
      <svg
        className="sparkline"
        viewBox={`0 0 ${path.w} ${path.h}`}
        role="img"
        aria-label="Review count history chart"
      >
        <path d={path.d} fill="none" stroke="currentColor" strokeWidth="2.5" />
      </svg>
      <div className="sparkline-scale">
        <span>{path.max.toLocaleString("en-GB")}</span>
        <span>{path.min.toLocaleString("en-GB")}</span>
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
  const [notesDraft, setNotesDraft] = useState("");
  const [notesSaving, setNotesSaving] = useState(false);
  const [notesMessage, setNotesMessage] = useState<string | null>(null);
  const [notesError, setNotesError] = useState<string | null>(null);
  const [historyBusy, setHistoryBusy] = useState(false);
  const [pricePage, setPricePage] = useState(0);
  const [reviewPage, setReviewPage] = useState(0);

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
    getProductDetail(asin, { historyDays: HISTORY_WINDOW_DAYS })
      .then((data) => {
        if (!cancelled) {
          setDetail(data);
          setNotesDraft(data.notes || "");
          setPricePage(0);
          setReviewPage(0);
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

  const shiftHistory = async (direction: "older" | "newer") => {
    if (!detail?.history_start || !detail.history_end) return;
    const nextEnd =
      direction === "older"
        ? addDaysIso(detail.history_start, -1)
        : addDaysIso(detail.history_end, HISTORY_WINDOW_DAYS) < todayIso()
          ? addDaysIso(detail.history_end, HISTORY_WINDOW_DAYS)
          : todayIso();
    setHistoryBusy(true);
    setError(null);
    try {
      const data = await getProductDetail(asin, {
        historyDays: HISTORY_WINDOW_DAYS,
        historyEnd: nextEnd,
      });
      setDetail({ ...data, notes: detail.notes });
      setPricePage(0);
      setReviewPage(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history");
    } finally {
      setHistoryBusy(false);
    }
  };

  const delta = formatPriceChange(
    detail?.price_change_absolute ?? null,
    detail?.price_change_percent ?? null,
  );
  const onSaveNotes = async () => {
    if (!detail) return;
    setNotesSaving(true);
    setNotesMessage(null);
    setNotesError(null);
    try {
      const result = await updateProductNotes(detail.asin, notesDraft);
      setDetail({ ...detail, notes: result.notes });
      setNotesDraft(result.notes || "");
      setNotesMessage("Notes saved.");
    } catch (err) {
      setNotesError(err instanceof Error ? err.message : "Failed to save notes");
    } finally {
      setNotesSaving(false);
    }
  };

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
                  <span className="metric-label">7-day price change</span>
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

          <section className="detail-panel notes-editor">
            <h2>Notes</h2>
            <p className="note">
              Notes stay with this product across every category list.
            </p>
            <textarea
              value={notesDraft}
              onChange={(e) => setNotesDraft(e.target.value)}
              rows={4}
              placeholder="Add a note about this product…"
              disabled={notesSaving}
            />
            {notesMessage ? <p className="note">{notesMessage}</p> : null}
            {notesError ? <p className="error">{notesError}</p> : null}
            <div className="notes-editor-actions">
              <button
                type="button"
                className="button compact"
                disabled={notesSaving}
                onClick={onSaveNotes}
              >
                {notesSaving ? "Saving…" : "Save notes"}
              </button>
            </div>
          </section>

          <section className="detail-panel">
            <h2>Product details</h2>
            <p className="note">
              Snapshot from the latest category or watchlist update for this
              product.
            </p>
            <dl className="detail-grid">
              <div>
                <dt>Best Sellers Rank</dt>
                <dd>{formatBsr(detail.bsr)}</dd>
              </div>
              <div>
                <dt>Bought past month</dt>
                <dd>
                  {formatMonthlySold(detail.monthly_sold)}
                  <span className="asin">Amazon badge (lower bound)</span>
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
                <dt>Reviews added</dt>
                <dd>
                  {formatReviewsAdded(detail.reviews_added)} today
                  {detail.reviews_added_7d != null
                    ? ` · ${formatReviewsAdded(detail.reviews_added_7d)} / 7d`
                    : ""}
                </dd>
              </div>
              <div>
                <dt>Review momentum</dt>
                <dd className={formatReviewMomentum(detail.review_momentum).className}>
                  {formatReviewMomentum(detail.review_momentum).text}
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

          <section className="detail-panel" data-testid="price-history">
            <h2>Price history</h2>
            <p className="note">
              Last 7 days on load. Use Older / Newer to page more history
              without loading the full series.
            </p>
            <HistoryRangePager
              start={detail.history_start}
              end={detail.history_end}
              hasOlder={detail.history_has_older}
              hasNewer={detail.history_has_newer}
              busy={historyBusy}
              onOlder={() => void shiftHistory("older")}
              onNewer={() => void shiftHistory("newer")}
            />
            <PriceSparkline points={detail.price_history} />
            {detail.price_history.length === 0 ? (
              <p className="note">
                No price points in this date range. It appears after products
                are updated and daily checks run.
              </p>
            ) : (
              <>
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
                      {pageSlice(
                        [...detail.price_history].reverse(),
                        pricePage,
                        HISTORY_TABLE_PAGE_SIZE,
                      ).rows.map((point) => (
                        <tr key={`${point.date}-${point.source}`}>
                          <td>{point.date}</td>
                          <td>{formatPrice(point.price, point.currency)}</td>
                          <td>{formatPriceHistorySource(point.source)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <TablePager
                  page={
                    pageSlice(
                      detail.price_history,
                      pricePage,
                      HISTORY_TABLE_PAGE_SIZE,
                    ).page
                  }
                  pages={
                    pageSlice(
                      detail.price_history,
                      pricePage,
                      HISTORY_TABLE_PAGE_SIZE,
                    ).pages
                  }
                  busy={historyBusy}
                  onChange={setPricePage}
                />
              </>
            )}
          </section>

          <section className="detail-panel" data-testid="review-history">
            <h2>Review momentum</h2>
            <p className="note">
              Daily rating counts from Amazon UK mobile pages. The day-over-day
              change is a demand signal, not unit sales.
            </p>
            <HistoryRangePager
              start={detail.history_start}
              end={detail.history_end}
              hasOlder={detail.history_has_older}
              hasNewer={detail.history_has_newer}
              busy={historyBusy}
              onOlder={() => void shiftHistory("older")}
              onNewer={() => void shiftHistory("newer")}
            />
            {(detail.review_history ?? []).length === 0 ? (
              <p className="note">
                No review history in this date range. Watchlist products pick
                this up on the next daily mobile check.
              </p>
            ) : (
              <>
                <ReviewSparkline points={detail.review_history ?? []} />
                <div className="table-wrap detail-history">
                  <table className="product-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Reviews</th>
                        <th>Added</th>
                        <th>Rating</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pageSlice(
                        [...(detail.review_history ?? [])].reverse(),
                        reviewPage,
                        HISTORY_TABLE_PAGE_SIZE,
                      ).rows.map((point) => (
                        <tr key={`${point.date}-${point.source}`}>
                          <td>{point.date}</td>
                          <td>{point.review_count.toLocaleString("en-GB")}</td>
                          <td>{formatReviewsAdded(point.reviews_added)}</td>
                          <td>
                            {point.rating != null ? point.rating.toFixed(1) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <TablePager
                  page={
                    pageSlice(
                      detail.review_history ?? [],
                      reviewPage,
                      HISTORY_TABLE_PAGE_SIZE,
                    ).page
                  }
                  pages={
                    pageSlice(
                      detail.review_history ?? [],
                      reviewPage,
                      HISTORY_TABLE_PAGE_SIZE,
                    ).pages
                  }
                  busy={historyBusy}
                  onChange={setReviewPage}
                />
              </>
            )}
          </section>
        </>
      ) : null}
    </main>
  );
}
