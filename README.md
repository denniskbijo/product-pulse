# Amazon Pulse (Product Pulse)

Amazon UK product research MVP: browse category top sellers, maintain a personal Watchlist, and run **Seasonal Hunt** discovery via Oxylabs. Easyparser enriches Watchlist / category sync within a 100-credit monthly budget.

## Architecture

- **Discover (bestsellers)** — parse `amazon.co.uk/gp/bestsellers/...` HTML (0 Easyparser credits)
- **Enrich** — Easyparser `DETAIL` for Watchlist ASIN paste and weekly category sync (admin)
- **Seasonal Hunt** — Oxylabs Amazon SEARCH / bestsellers (1 Oxylabs result per run; no Easyparser fallback). Results auto-save to the `seasonal-hunt` category
- **Weekly history** — `product_snapshots` for BSR, sales estimates, and week-vs-week fallback
- **Daily prices** — Amazon mobile pages (`/gp/aw/d/{ASIN}`) via `make scrape-prices` / Vercel Cron (no Easyparser)

```
amazon-pulse/
  apps/api/     # FastAPI + sync / hunt workers
  apps/web/     # Next.js dashboard
  docker-compose.yml
```

## Prerequisites

1. Docker (optional Postgres)
2. Python 3.11+
3. Node.js 20+
4. Easyparser API key (Watchlist / category sync): https://app.easyparser.com/signup
5. Oxylabs credentials (Seasonal Hunt): https://developers.oxylabs.io/

## Setup

```bash
cp .env.example .env
# set EASYPARSER_API_KEY, OXYLABS_USERNAME, OXYLABS_PASSWORD
# set JWT_SECRET, ADMIN_PASSWORD_HASH, USER_PASSWORD_HASH

# Generate password hashes (never store plaintext passwords):
cd apps/api && .venv/bin/python -c "from app.passwords import hash_password; print(hash_password('your-password'))"

# Optional Postgres (otherwise SQLite file amazon_pulse.db is used):
# docker compose up -d
# then set DATABASE_URL=postgresql+psycopg://amazon_pulse:amazon_pulse@localhost:5432/amazon_pulse

make install   # once
make run       # API :8000 + web :3000
```

Open http://localhost:3000 and sign in.

| Role | Can run Seasonal Hunt | Can sync categories / paste Watchlist ASINs | Sees Easyparser credits |
|---|---|---|---|
| Admin | Yes | Yes | Yes |
| User | Yes | No | No (sees last sync time + products) |

Anyone must log in to view products. Tokens are JWTs; the API CORS allowlist must include your web origin (never `*`).

Other targets: `make api`, `make web`, `make test`, `make scrape-prices`, `make db-pull`.

### Auth & CORS

```
JWT_SECRET=...
ADMIN_USERNAME=admin
ADMIN_PASSWORD_HASH=$2b$12$...
USER_USERNAME=basil
USER_PASSWORD_HASH=$2b$12$...
API_CORS_ORIGINS=http://localhost:3000
```

Login is rate-limited (10 attempts / 15 minutes per IP and per username). Plaintext `ADMIN_PASSWORD` / `USER_PASSWORD` are ignored.

### Copy production DB to local

```bash
make db-pull
```

Copies Neon production tables into your local `DATABASE_URL` (default SQLite). Backs up an existing SQLite file first.

Source URL resolution order:
1. `PROD_DATABASE_URL` (or `DATABASE_URL_PROD`) in `.env`
2. `vercel env pull` from the linked `apps/api` project (`product-pulse-api`)

### Daily price scrape (local / cron)

```bash
make scrape-prices
```

Picks up to `DAILY_SCRAPE_MAX` (default 10) unique ASINs from the latest weekly snapshot set, fetches each mobile product page with `DAILY_SCRAPE_DELAY_SECONDS` between requests, and upserts `daily_price_points`.

On Vercel, daily prices are triggered by Cron → `GET /cron/daily-prices` with `Authorization: Bearer <CRON_SECRET>`. In-process APScheduler only runs on long-lived local hosts (not serverless).

## Seasonal Hunt

Four seasons (Winter → Summer → Autumn → Spring procure-ahead defaults). Any signed-in user can run a hunt.

- Provider: **Oxylabs only** (1 request reserved against `OXYLABS_MONTHLY_CREDIT_BUDGET` before the call)
- Failed Oxylabs calls still consume the reserved credit (conservative)
- Concurrent hunts cannot race past the monthly budget (atomic ledger update)
- Results auto-save to category slug `seasonal-hunt` (legacy `winter-hunt` is migrated on seed)
- Promoting a hunt hit to Watchlist uses hunt data (**0 Easyparser credits**)

```
OXYLABS_USERNAME=...
OXYLABS_PASSWORD=...
OXYLABS_MONTHLY_CREDIT_BUDGET=1000
HUNT_TOP_N=5
```

## Deploy on Vercel

| App | URL |
|---|---|
| **Web dashboard** | https://product-pulse-six.vercel.app |
| **API** | https://product-pulse-api-kappa.vercel.app |

Two Vercel projects:

1. **API** (`apps/api`) — FastAPI serverless (London `lhr1`) + Neon Postgres
2. **Web** (`apps/web`) — Next.js (`NEXT_PUBLIC_API_URL` → API)

### Redeploy

```bash
# API
cd apps/api && npx vercel --prod --yes

# Web
cd apps/web && npx vercel --prod --yes
```

Required API env vars: `EASYPARSER_API_KEY`, `DATABASE_URL`, `JWT_SECRET`, `ADMIN_PASSWORD_HASH`, `USER_PASSWORD_HASH`, `API_CORS_ORIGINS` (e.g. `https://product-pulse-six.vercel.app,http://localhost:3000`), `CRON_SECRET`, Oxylabs credentials + `OXYLABS_MONTHLY_CREDIT_BUDGET`.

Do **not** set `API_CORS_ORIGINS=*`.

## API (selected)

| Method | Path | Description |
|---|---|---|
| POST | `/auth/login` | Login (rate-limited) |
| GET | `/categories` | Seeded UK categories |
| GET | `/categories/{id\|slug}/top?window=7d` | Top products + sync/credit status |
| POST | `/categories/{id\|slug}/sync` | Discover → enrich → snapshot (admin) |
| GET/POST | `/hunt/...` | Seasonal Hunt meta + run |
| GET | `/cron/daily-prices` | Cron-triggered daily price scrape |
| GET | `/health` | Health check |

## Easyparser credit budget

Default monthly budget is **100** (Easyparser Demo). Weekly sync of one category uses ~11 credits (discover is free; 10× DETAIL). Sync hard-stops when the local budget would be exceeded.

```
EASYPARSER_API_KEY=...
MONTHLY_CREDIT_BUDGET=100
SYNC_TOP_N=10
```

Local Monday 06:00 APScheduler syncs the first bestsellers category when an API key is present (not on Vercel serverless).

## Sales estimates

1. Prefer Amazon “bought in past month” when returned → `weekly ≈ monthly / 4.3`
2. Else UK Home & Kitchen BSR power-curve estimate
3. Always labeled in the UI (`monthly_sold` / `bsr_curve`)

These are **estimates**, not Amazon’s private unit sales.

## Tests

```bash
make test
# or:
cd apps/api && source .venv/bin/activate && pytest
```
