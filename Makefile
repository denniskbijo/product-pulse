SHELL := /bin/bash
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
API_DIR := $(ROOT)/apps/api
WEB_DIR := $(ROOT)/apps/web
VENV := $(API_DIR)/.venv
PYTHON := $(VENV)/bin/python
UVICORN := $(VENV)/bin/uvicorn
API_PORT ?= 8000
WEB_PORT ?= 3000

.PHONY: help install run dev api web test test-ui test-ui-install scrape-prices db-pull stop

help:
	@echo "Amazon Pulse / product-pulse"
	@echo ""
	@echo "  make install        Install API + web dependencies"
	@echo "  make run            Start API (:$(API_PORT)) and web (:$(WEB_PORT)) together"
	@echo "  make api            Start API only"
	@echo "  make web            Start Next.js only"
	@echo "  make test           Run API unit tests"
	@echo "  make test-ui        Run mocked Playwright UI tests"
	@echo "  make test-ui-install  Install Playwright Chromium (once)"
	@echo "  make scrape-prices  Daily Amazon mobile price + Watchlist review scrape"
	@echo "  make db-pull        Copy production Neon DB into local DATABASE_URL"
	@echo ""
	@echo "Requires .env with EASYPARSER_API_KEY (see .env.example)."

install: $(VENV)/bin/uvicorn $(WEB_DIR)/node_modules

$(VENV)/bin/uvicorn: $(API_DIR)/requirements.txt
	@test -x $(PYTHON) || python3 -m venv $(VENV)
	$(VENV)/bin/pip install -r $(API_DIR)/requirements.txt

$(WEB_DIR)/node_modules: $(WEB_DIR)/package.json
	cd $(WEB_DIR) && npm install
	@touch $(WEB_DIR)/node_modules

# One command: API + dashboard. Ctrl+C stops both.
run dev: install
	@test -f $(ROOT)/.env || (echo "Missing .env — copy .env.example and set EASYPARSER_API_KEY"; exit 1)
	@set -euo pipefail; \
	set -a; source $(ROOT)/.env; set +a; \
	export NEXT_PUBLIC_API_URL="$${NEXT_PUBLIC_API_URL:-http://localhost:$(API_PORT)}"; \
	$(UVICORN) app.main:app --app-dir $(API_DIR) --reload --host 0.0.0.0 --port $(API_PORT) & \
	api_pid=$$!; \
	cd $(WEB_DIR) && npm run dev -- --port $(WEB_PORT) & \
	web_pid=$$!; \
	trap 'kill $$api_pid $$web_pid 2>/dev/null; wait $$api_pid $$web_pid 2>/dev/null' INT TERM EXIT; \
	echo ""; \
	echo "API  → http://localhost:$(API_PORT)"; \
	echo "Web  → http://localhost:$(WEB_PORT)"; \
	echo "Press Ctrl+C to stop both."; \
	echo ""; \
	wait

api: install
	@test -f $(ROOT)/.env || (echo "Missing .env — copy .env.example and set EASYPARSER_API_KEY"; exit 1)
	@set -a; source $(ROOT)/.env; set +a; \
	cd $(API_DIR) && $(UVICORN) app.main:app --reload --host 0.0.0.0 --port $(API_PORT)

web: install
	@set -a; source $(ROOT)/.env 2>/dev/null || true; set +a; \
	export NEXT_PUBLIC_API_URL="$${NEXT_PUBLIC_API_URL:-http://localhost:$(API_PORT)}"; \
	cd $(WEB_DIR) && npm run dev -- --port $(WEB_PORT)

test: install
	cd $(API_DIR) && $(VENV)/bin/pytest -q

test-ui-install:
	cd $(WEB_DIR) && npm install && npx playwright install chromium

test-ui: $(WEB_DIR)/node_modules
	cd $(WEB_DIR) && npx playwright test

# Local/cron: scrape prices + Watchlist review counts via Amazon mobile pages (no Easyparser).
scrape-prices: install
	@set -a; source $(ROOT)/.env 2>/dev/null || true; set +a; \
	cd $(API_DIR) && $(PYTHON) -m app scrape-prices

# Replace local DB with a copy of production (Neon). Uses PROD_DATABASE_URL or Vercel env pull.
db-pull: install
	@set -a; source $(ROOT)/.env 2>/dev/null || true; set +a; \
	cd $(API_DIR) && $(PYTHON) -m app pull-prod-db

