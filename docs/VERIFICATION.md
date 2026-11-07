# Verification record — 5 November 2026

## Executed successfully

- Backend: `python -m pytest tests -q` — **7 passed**. Uses isolated SQLite sessions and actual models/tools. Covers login, registration/roles, unauthorized writes, products, inventory adjustment constraints, chronological forecast evaluation, supplier comparisons, safety stock/reorder calculations, pack/budget/capacity optimization, import preview/mapping/rollback, draft creation, one-time approval, LangGraph execution, recorded tool calls, and deterministic assistant evidence.
- Frontend: TypeScript `tsc -b` — passed.
- Frontend: Vitest / React Testing Library — **2 passed** (51 unique page routes; search and pagination interaction).
- Frontend: Vite production build — passed. Initial sandbox-only attempts failed because esbuild could not read ancestor directories; the same build succeeded with process permission.
- Playwright Chromium workflow — **1 passed** on final rerun, 26.1 seconds total: local demo login, dashboard forecast, agent draft, explicit review checkbox, authenticated approval. Uses the installed full Chromium browser. Initial default headless-shell launch failed because that executable was absent; configured the installed `chromium` channel and reran successfully.
- Browser UI inspection separately confirmed dashboard data, held-out forecast results, workflow awaiting approval, and approved local order with approver ID.
- Live HTTP readiness: frontend `/` returned 200; API `/api/health` returned OK on port 8011.
- Alembic: upgrade on a fresh scratch SQLite database and `alembic check` passed: **No new upgrade operations detected**.
- PowerShell startup script parsed without syntax errors. The two underlying server commands were run and HTTP-checked separately; the background launcher itself was not integration-tested.

## Environment and limits

Local Python 3.15.2, Node 24.22.1. Python packages installed in project `.venv`. Dependency installation required `PYYAML_FORCE_LIBYAML=0` to avoid an unavailable C++ compiler. Runtime emitted upstream Starlette test-client and LangGraph asyncio deprecation warnings; tests passed. A machine-specific tested freeze is in `backend/requirements.lock.txt`; use the broader requirements file on Python 3.12 rather than assuming every Python 3.15 freeze version supports older Python.

The original port 8000 was occupied by another application. StockPilot's local API uses 8011 and Vite proxies there. The demo database contains synthetic records and local orders created during browser verification. A repeated browser run was interrupted after its original fixed-product precondition ceased to hold: earlier approvals correctly increased confirmed incoming stock. The specification now selects a product with a current feasible replenishment need rather than assuming the same product always needs another order.

Docker deployment was not run (Docker unavailable). PostgreSQL was subsequently deployed through the approved Neon Free integration and initialized by successful cloud Alembic migrations. A real LLM/provider and supplier integration were not tested (no credentials/integration provided). Forecast statistical calibration beyond the reported held-out sample is not claimed. See README scope limitations for remaining production work; this verification does not certify the entire master brief as production complete.

## Vercel follow-up

- Backend suite including the one-time cloud administrator bootstrap: **8 passed**.
- TypeScript and production frontend build passed after adding the setup screen.
- Official Vercel production build completed, including Python 3.12 dependencies, frontend build and PostgreSQL migrations.
- Production `/api/health`: HTTP 200.
- Browser-style HTML requests to `/`, `/demand-forecasting`, and `/inventory-dashboard`: HTTP 200. Non-HTML requests do not receive the SPA fallback.
- Invalid bootstrap token: HTTP 403. Unauthenticated inventory request: HTTP 401.
- Browser inspection confirmed the deployed dashboard signed in with an administrator, initially with zero inventory records. No local users or SQLite data were uploaded.
- Neon billing metadata confirmed `free_v3`, named Free, no payment method required.

## Agent cloud timeout follow-up

The unbatched risk tool exceeded its 30-second deadline against PostgreSQL. The workflow now loads products, stock, recent sales, supplier offers, delivery performance, and confirmed incoming quantities in seven bounded queries and reuses that per-run snapshot. This avoids repeated cross-region queries in each agent. Vercel is configured for `iad1`, near the database's US region.

- Backend: **10 passed**, including snapshot parity, query-count bounds, and rejecting analyst draft requests before execution.
- Browser regressions: **4 passed**, including sample-data refresh, permissions, analyst analysis access, and preserving the draft-ready result through refresh.
- Real PostgreSQL verification in a rolled-back transaction: **awaiting_approval**, actual draft generated, **10.68 seconds**, no test order committed.
- The UI now distinguishes failed execution, completed analysis, and a draft awaiting approval. Analyst accounts cannot invoke draft creation; administrators, approvers, and planners retain that permission.
