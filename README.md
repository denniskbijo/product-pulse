# Amazon Pulse

Amazon UK product research MVP: discover category top sellers from public Best Sellers pages, enrich with Easyparser (free 100 credits/month), and show price, estimated weekly volume, and week-over-week price changes.

## Architecture

- **Discover** — parse `amazon.co.uk/gp/bestsellers/...` HTML (0 Easyparser credits)
- **Enrich** — Easyparser `DETAIL` for the top 10 ASINs (~10 credits/week)
- **History** — Postgres weekly snapshots for WoW price deltas

```
amazon-pulse/
  apps/api/     # FastAPI + sync worker
  apps/web/     # Next.js dashboard
  docker-compose.yml
```

## Prerequisites

1. Docker (Postgres)
2. Python 3.11+
3. Node.js 20+
4. Free Easyparser API key: https://app.easyparser.com/signup

## Setup

```bash
cp .env.example .env
# set EASYPARSER_API_KEY=...

# Optional Postgres (otherwise SQLite file amazon_pulse.db is used):
# docker compose up -d
# then set DATABASE_URL=postgresql+psycopg://amazon_pulse:amazon_pulse@localhost:5432/amazon_pulse

cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# new terminal
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000

## API

| Method | Path | Description |
|---|---|---|
| GET | `/categories` | Seeded UK categories |
| GET | `/categories/{id\|slug}/top?window=7d` | Top 10 + sync/credit status |
| POST | `/categories/{id\|slug}/sync` | Run discover → enrich → snapshot now |
| GET | `/health` | Health check |

## Credit budget

Default monthly budget is **100** (Easyparser Demo). Weekly sync of one category uses ~11 credits (discover is free; 10× DETAIL). The sync hard-stops when the local budget would be exceeded.

Configure via `.env`:

```
EASYPARSER_API_KEY=...
MONTHLY_CREDIT_BUDGET=100
SYNC_TOP_N=10
DATABASE_URL=postgresql+psycopg://amazon_pulse:amazon_pulse@localhost:5432/amazon_pulse
```

A Monday 06:00 cron job syncs the first seeded category (Home & Kitchen) when an API key is present.

## Sales estimates

1. Prefer Amazon “bought in past month” when Easyparser returns it → `weekly ≈ monthly / 4.3`
2. Else UK Home & Kitchen BSR power-curve estimate
3. Always labeled in the UI (`monthly_sold` / `bsr_curve`)

These are **estimates**, not Amazon’s private unit sales.

## Tests

```bash
cd apps/api
source .venv/bin/activate
pytest
```
