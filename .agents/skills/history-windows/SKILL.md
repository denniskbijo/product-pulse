---
name: history-windows
description: Default product charts and history tables to the last 7 days, paginate older windows via API, and keep first-load queries small. Use when adding time-series charts, price/review history tables, date-range controls, or any feature that would otherwise return a long daily series.
---

# History windows

Time-series UI in this app loads **the last 7 days on first paint**. Older data is fetched only when the user pages the date range. Do not return 30+ daily rows on every product load.

## Rules

1. **Default window is 7 inclusive days** ending today (`history_days=7`).
2. **Paginate older/newer windows** with `history_end` (ISO date). Older = end just before the current `history_start`. Newer = shift forward by `history_days`, capped at today.
3. **Charts show only the current window.** Do not chart the full stored series.
4. **Tables paginate rows** inside the window (5 per page) and share the same Older / Newer range control.
5. **Keep summary metrics independent of the window.** Latest price, 7-day price change, review count, and momentum always use the latest data, not the paged window.
6. **Tell the client if more exists:** `history_has_older` if any successful points exist before `history_start`. `history_has_newer` if `history_end` is before today, so the user can always return to the latest window even when recent days are empty.

## API

`GET /products/{asin}?history_days=7&history_end=YYYY-MM-DD`

Response fields: `history_days`, `history_start`, `history_end`, `history_has_older`, `history_has_newer`, plus the windowed `price_history` / `review_history`.

Cap `history_days` at 31. Reuse `HISTORY_WINDOW_DAYS_DEFAULT` and `history_window_bounds()` in `apps/api/app/services.py`.

## Frontend

`getProductDetail(asin, { historyDays, historyEnd })` in `apps/web/lib/api.ts`. Constants: `HISTORY_WINDOW_DAYS` (7), `HISTORY_TABLE_PAGE_SIZE` (5).

Wide list tables (Watchlist) must scroll inside `.table-wrap` (`max-width: 100%; overflow-x: auto`). Do not let extra columns clip against `overflow-x: hidden` on the page.

## New features

If you add another daily series (units, BSR, ads), follow this same 7-day window + range pager + table pager. Do not add a new unbounded history dump.
