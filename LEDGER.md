# Project ledger

Index of initiatives. **Beads** (`bd`) is the task tracker; this file is the map.

| Item | Status | Bead |
|---|---|---|
| Watchlist review momentum (mobile daily scrape) | Shipped | amazon-pulse-sir |
| 7-day history windows + table pagination | In tree, uncommitted | amazon-pulse-pf2 |
| Mobile layout for Watchlist + history pagers | Done | amazon-pulse-4e5 |
| Playwright UI tests (mocked API) | Done | amazon-pulse-9vr |
| Run UI tests on local push to main | Done | amazon-pulse-ypb |
| Competition category + Easyparser review history (admin) | Open / roadmap | amazon-pulse-5qe |
| Daily / weekly / monthly units sold on Watchlist | Open | amazon-pulse-7n4 |
| Rotate expired GitHub Actions `VERCEL_TOKEN` | Open | amazon-pulse-3m7 |

## How to work an item

```bash
bd show <id>
bd update <id> --claim
# …do the work…
bd close <id>
```

New initiatives go here **and** in beads. Do not treat this file as a TODO list of implementation steps.

## Local gates

- `make test` — API unit tests
- `make test-ui` — mocked Playwright UI tests (login, Watchlist desktop/mobile, history windows)
- `make test-ui-install` — one-time Chromium install
- Pushing to `main` runs `make test-ui` via `.beads/hooks/pre-push`
