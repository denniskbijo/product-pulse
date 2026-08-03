"use client";

import { useEffect, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import {
  addWatchlistProduct,
  Category,
  CategoryTop,
  getCategories,
  getCategoryTop,
  removeProductFromCategory,
  TopProduct,
  triggerSync,
  updateProductNotes,
} from "@/lib/api";
import { clearSession, isAdmin, loadSession, type Session } from "@/lib/auth";
import { formatBsr, formatPriceChange } from "@/lib/labels";

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

function formatWhen(value: string | null) {
  if (!value) return "Never";
  return new Date(value).toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
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
        <a
          href={`/products/${encodeURIComponent(product.asin)}`}
          target="_blank"
          rel="noreferrer"
        >
          {product.title || product.asin}
        </a>
        <span className="asin">{product.asin}</span>
        {product.notes ? (
          <span className="product-notes">{product.notes}</span>
        ) : null}
      </div>
    </div>
  );
}

function ProductActions({
  product,
  busy,
  onEditNotes,
  onDelete,
}: {
  product: TopProduct;
  busy: boolean;
  onEditNotes: (product: TopProduct) => void;
  onDelete: (product: TopProduct) => void;
}) {
  return (
    <div className="product-actions">
      <button
        type="button"
        className="button secondary compact"
        disabled={busy}
        onClick={() => onEditNotes(product)}
      >
        Edit notes
      </button>
      <button
        type="button"
        className="button danger compact"
        disabled={busy}
        onClick={() => onDelete(product)}
      >
        Delete
      </button>
    </div>
  );
}

export default function HomePage() {
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selected, setSelected] = useState<string>("watchlist");
  const [data, setData] = useState<CategoryTop | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();
  const [syncing, setSyncing] = useState<"full" | "one" | null>(null);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [watchlistInput, setWatchlistInput] = useState("");
  const [addingWatchlist, setAddingWatchlist] = useState(false);
  const [watchlistAddMessage, setWatchlistAddMessage] = useState<string | null>(
    null,
  );
  const [watchlistAddError, setWatchlistAddError] = useState<string | null>(null);
  const [actionAsin, setActionAsin] = useState<string | null>(null);
  const [notesEditor, setNotesEditor] = useState<{
    asin: string;
    title: string;
    notes: string;
  } | null>(null);
  const [notesSaving, setNotesSaving] = useState(false);
  const [notesError, setNotesError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TopProduct | null>(null);
  const [deleting, setDeleting] = useState(false);

  const admin = isAdmin(session);
  const hasProducts = (data?.products.length ?? 0) > 0;
  const isWatchlist = selected === "watchlist";

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
          cats.find((c) => c.slug === "watchlist")?.slug ||
          cats.find((c) => c.slug === "home-kitchen")?.slug ||
          cats[0]?.slug;
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

  const onAddWatchlist = async () => {
    const input = watchlistInput.trim();
    if (!input) return;
    setAddingWatchlist(true);
    setWatchlistAddMessage(null);
    setWatchlistAddError(null);
    try {
      const result = await addWatchlistProduct(input);
      if (result.status === "success") {
        setWatchlistAddMessage(result.message);
        setWatchlistInput("");
        if (selected !== "watchlist") {
          setSelected("watchlist");
        }
        load("watchlist");
      } else if (result.status === "budget_exceeded" && !admin) {
        setWatchlistAddError(
          "Monthly product lookup limit reached. Contact an admin.",
        );
      } else {
        setWatchlistAddError(result.message);
      }
    } catch (err) {
      setWatchlistAddError(
        err instanceof Error ? err.message : "Failed to add product",
      );
    } finally {
      setAddingWatchlist(false);
    }
  };

  const onEditNotes = (product: TopProduct) => {
    setNotesError(null);
    setNotesEditor({
      asin: product.asin,
      title: product.title || product.asin,
      notes: product.notes || "",
    });
  };

  const onSaveNotes = async () => {
    if (!notesEditor) return;
    setNotesSaving(true);
    setNotesError(null);
    try {
      await updateProductNotes(notesEditor.asin, notesEditor.notes);
      setNotesEditor(null);
      load(selected);
    } catch (err) {
      setNotesError(err instanceof Error ? err.message : "Failed to save notes");
    } finally {
      setNotesSaving(false);
    }
  };

  const onConfirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    setActionAsin(deleteTarget.asin);
    setError(null);
    try {
      await removeProductFromCategory(selected, deleteTarget.asin);
      setDeleteTarget(null);
      load(selected);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to remove product");
    } finally {
      setDeleting(false);
      setActionAsin(null);
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
            <span className="note">{session.username}</span>
            <button className="button secondary compact" onClick={onLogout}>
              Log out
            </button>
          </div>
        </div>
        <p className="lede">
          {isWatchlist
            ? "Your custom watchlist — paste an ASIN or Amazon UK product link to add it."
            : "UK category top sellers — current price, estimated weekly volume, and 7-day price changes."}
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
          {isWatchlist ? (
            <>
              <div className="field field-watchlist">
                <label htmlFor="watchlist-input">ASIN or Amazon UK URL</label>
                <input
                  id="watchlist-input"
                  type="text"
                  placeholder="B0… or amazon.co.uk/dp/…"
                  value={watchlistInput}
                  onChange={(event) => setWatchlistInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      void onAddWatchlist();
                    }
                  }}
                  disabled={addingWatchlist || pending}
                />
              </div>
              <button
                className="button"
                onClick={() => void onAddWatchlist()}
                disabled={addingWatchlist || pending || !watchlistInput.trim()}
              >
                {addingWatchlist ? "Adding…" : "Add product"}
              </button>
            </>
          ) : null}
          {admin && !isWatchlist ? (
            <>
              <button
                className={hasProducts ? "button secondary" : "button"}
                onClick={() => onSync(1)}
                disabled={syncing != null || pending}
                title="Refresh details for the #1 product in this category"
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
        {watchlistAddMessage ? (
          <p className="note">{watchlistAddMessage}</p>
        ) : null}
        {watchlistAddError ? (
          <p className="error">{watchlistAddError}</p>
        ) : null}
      </section>

      {!hasProducts && isWatchlist ? (
        <section className="empty-cta">
          <h2>No watchlist products yet</h2>
          <p className="note">
            Watchlist is your custom list. Paste an ASIN or Amazon UK URL above to
            add one product at a time.
          </p>
        </section>
      ) : null}

      {!hasProducts && admin && !isWatchlist ? (
        <section className="empty-cta">
          <h2>No products yet</h2>
          <p className="note">
            Run a sync to load this category’s top sellers. Results will then be
            available for everyone signed in.
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
          Last updated:{" "}
          <strong>{formatWhen(data?.sync.last_sync_at ?? null)}</strong>
        </div>
        {data?.note ? <p className="note">{data.note}</p> : null}
        {error ? <p className="error">{error}</p> : null}
        {admin ? (
          <details className="system-details">
            <summary>System details</summary>
            <div className="system-details-body">
              {!isWatchlist && data?.sync.last_status ? (
                <div>
                  Last sync status: <strong>{data.sync.last_status}</strong>
                </div>
              ) : null}
              {creditLabel ? (
                <div>
                  Enrichment credits: <strong>{creditLabel}</strong>
                  {credits?.credits_remaining_reported != null
                    ? ` · provider reports ${credits.credits_remaining_reported} remaining`
                    : ""}
                </div>
              ) : null}
              {syncMessage ? <p className="note">{syncMessage}</p> : null}
              {data?.sync.last_error ? (
                <p className="error">Last sync error: {data.sync.last_error}</p>
              ) : null}
            </div>
          </details>
        ) : null}
      </section>

      <section className="products-section">
        {!data || data.products.length === 0 ? (
          <div className="empty">
            {pending ? "Loading…" : "No products in this list yet."}
          </div>
        ) : (
          <>
            <ul className="product-cards">
              {data.products.map((product) => {
                const delta = formatPriceChange(
                  product.price_change_absolute,
                  product.price_change_percent,
                );
                const busy = actionAsin === product.asin;
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
                        <dt>7-day price change</dt>
                        <dd className={delta.className}>{delta.text}</dd>
                      </div>
                      <div>
                        <dt>Est. weekly units</dt>
                        <dd>
                          {product.estimated_weekly_units != null
                            ? `~${product.estimated_weekly_units}`
                            : "—"}
                        </dd>
                      </div>
                      <div>
                        <dt>Best Sellers Rank</dt>
                        <dd>{formatBsr(product.bsr)}</dd>
                      </div>
                    </dl>
                    <ProductActions
                      product={product}
                      busy={busy}
                      onEditNotes={onEditNotes}
                      onDelete={setDeleteTarget}
                    />
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
                    <th>7-day price change</th>
                    <th>Est. weekly units</th>
                    <th>Best Sellers Rank</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.products.map((product) => {
                    const delta = formatPriceChange(
                      product.price_change_absolute,
                      product.price_change_percent,
                    );
                    const busy = actionAsin === product.asin;
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
                        </td>
                        <td>{formatBsr(product.bsr)}</td>
                        <td>
                          <ProductActions
                            product={product}
                            busy={busy}
                            onEditNotes={onEditNotes}
                            onDelete={setDeleteTarget}
                          />
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
        Weekly unit figures are estimates — from Amazon’s “bought in past month”
        when available, otherwise inferred from Best Sellers Rank. Prices update
        from regular checks; 7-day change uses recent daily history when we have
        it.
      </p>

      {notesEditor ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => {
            if (!notesSaving) setNotesEditor(null);
          }}
        >
          <div
            className="modal-panel notes-editor"
            role="dialog"
            aria-modal="true"
            aria-label="Edit product notes"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="notes-editor-head">
              <h2>Notes</h2>
              <p className="note">{notesEditor.title}</p>
            </div>
            <textarea
              value={notesEditor.notes}
              onChange={(e) =>
                setNotesEditor({ ...notesEditor, notes: e.target.value })
              }
              rows={4}
              placeholder="Add a note about this product…"
              disabled={notesSaving}
              autoFocus
            />
            {notesError ? <p className="error">{notesError}</p> : null}
            <div className="notes-editor-actions">
              <button
                type="button"
                className="button secondary compact"
                disabled={notesSaving}
                onClick={() => setNotesEditor(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button compact"
                disabled={notesSaving}
                onClick={onSaveNotes}
              >
                {notesSaving ? "Saving…" : "Save notes"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {deleteTarget ? (
        <div
          className="modal-backdrop"
          role="presentation"
          onClick={() => {
            if (!deleting) setDeleteTarget(null);
          }}
        >
          <div
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            aria-label="Confirm delete"
            onClick={(event) => event.stopPropagation()}
          >
            <h2>Remove product?</h2>
            <p className="note">
              Remove “{deleteTarget.title || deleteTarget.asin}” from this list?
              Price history is kept, and category syncs may add it back later.
            </p>
            <div className="notes-editor-actions">
              <button
                type="button"
                className="button secondary compact"
                disabled={deleting}
                onClick={() => setDeleteTarget(null)}
              >
                Cancel
              </button>
              <button
                type="button"
                className="button danger compact"
                disabled={deleting}
                onClick={() => void onConfirmDelete()}
              >
                {deleting ? "Removing…" : "Remove"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
