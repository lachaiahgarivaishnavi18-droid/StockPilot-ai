# StockPilot AI

A local full-stack academic inventory replenishment demonstrator: React/TypeScript, FastAPI, SQLAlchemy, forecasting model comparison, constrained replenishment, LangGraph application tools, and authenticated human approvals.

Hosted deployment: **https://stockpilot-ai-black.vercel.app**. The hosted workspace uses its own Neon PostgreSQL database and administrator account; local demo credentials do not apply. See `docs/VERCEL_DEPLOYMENT.md` for deployment configuration and maintenance.

## Start here (Windows PowerShell)

Dependencies and the synthetic demo account have already been prepared in this workspace. To reopen the local demo, run **`.\scripts\start.ps1`** from the project root, then visit http://127.0.0.1:5173. The following instructions are for a fresh installation.

From this project directory, prepare the backend:

```powershell
python -m venv .venv
$env:PYYAML_FORCE_LIBYAML = '0'
.\.venv\Scripts\python -m pip install -r backend/requirements.txt
cd backend
..\.venv\Scripts\python bootstrap.py --demo
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8011
```

In a second terminal, from the project directory:

```powershell
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173. Sign in as **demo@stockpilot.local**, password **StockPilot-demo-2026!**. This publicly documented account is for local demonstration only. The loader preserves existing products and never resets a database. Python 3.12 is recommended; Python 3.15 may need pure-Python PyYAML as shown above. If npm is unavailable in the Codex environment, use `scripts/frontend.ps1` instead.

## Demonstration walkthrough

1. Sign in. The executive overview shows database-derived inventory value, product counts, risk signals, and pending approvals.
2. Open **Data Import**. Choose products, sales, or inventory; choose CSV/JSON; map source column names using a JSON object. Validate/preview before committing. The import is atomic, rejects duplicate keys, and logs its history. Inventory replacement requires an approver and explicit confirmation.
3. Open **Demand Forecasting**. Select a product and generate a forecast. Inspect validation scores, held-out test metrics, history, predictions, intervals, and the selected model.
4. Open **Reorder Recommendations**. Calculate a plan with a budget and service level. Inspect reorder point, safety stock, EOQ, constraints and costs.
5. Open **Agent Dashboard**. Run analysis or explicitly run with draft creation. Click an execution row and expand evidence to inspect actual tool calls and structured outputs.
6. Open **Purchase Order Management**. Select a draft, review quantity and cost, check the review confirmation, and approve. Approval changes a local record, reserves supplier availability, and adds confirmed incoming inventory. It does not send an order to a supplier.
7. Ask the **Inventory AI Assistant** about a selected product. Without credentials it identifies itself as deterministic local mode and displays actual tool evidence.
8. Generate a report and inspect **Audit Logs**.

The one-click sample loader creates 12 synthetic products, 240 daily sales observations per product, 3 suppliers, a warehouse, product offers, batches, and delivery observations. No paid API is needed. See `data/samples` for upload schema examples; the two-row sales example illustrates the schema and is not sufficient for forecasting.

## Architecture and calculations

- `backend/app/models.py`: relational data models, indexed foreign keys and constraints.
- `backend/app/main.py`: authenticated REST endpoints and authorization boundaries. Interactive API schema: http://127.0.0.1:8011/docs.
- `backend/app/forecasting.py`: moving average, exponential smoothing, ARIMA, random forest and XGBoost candidates (data-dependent). Chronological train/validation/test blocks; model selection uses validation MAE. Test metrics never select the winner. Final production forecast refits the selected model on all observations. Lag predictors are recursively constructed without future observations. Intervals use a held-out absolute-error quantile; coverage is not guaranteed.
- `backend/app/services.py`: independent demand/lead-time safety stock, reorder point, EOQ, net requirement, supplier ranking, and pack-constrained piecewise-linear candidate optimization under MOQ, pack, availability, capacity and budget constraints. Units and cost assumptions accompany every result. Historical calculations are labeled; the orchestrator also generates a forecast-conditioned optimization.
- `backend/app/tools.py`: closed registry, Pydantic argument validation, permission checks, JSON output checks and invocation logs. No shell or arbitrary SQL tools. A 30-second elapsed deadline rejects overruns after execution; computation is not preempted. Provider requests have network timeouts. Hard worker cancellation remains future work.
- `backend/app/agents.py`: typed LangGraph state, real function tools, conditional failure/draft routes, per-run in-memory checkpoints and database execution history. Nodes are deterministic analytical agents in demo mode. Optional LLM tool selection is implemented in the assistant. Approval cannot be invoked through the registry.
- `frontend/src`: responsive sidebar with 51 navigable destinations using shared operational workspaces, search/pagination, light/dark theme, loading/errors, charts, forms and evidence panels.

## Configuration

Environment variables are read by the server process; `.env.example` is a reference, not automatically loaded by local Python. Use PowerShell `$env:NAME='value'` before starting the server. Production requires `JWT_SECRET` (random 32+ characters). Development uses an ephemeral signing secret, so sessions expire on restart. Configure `DATABASE_URL` for PostgreSQL (`postgresql+psycopg://...`) and install `psycopg[binary]`. Set `CORS_ORIGINS` to explicit frontend origins.

To enable a real LLM, set `OPENAI_API_KEY`, optionally `OPENAI_BASE_URL`, and `LLM_MODEL`. The assistant binds the same validated read/analysis tools, caps tool turns, requires tool evidence, and falls back explicitly when the provider fails. Provider credentials and network behavior have not been validated without an actual account. Provider prose is not a substitute for reviewing evidence.

New registrations always receive the analyst role. To create an administrator deliberately, run `python bootstrap.py --email your@email.example` in `backend` and enter a password interactively. There is no public role escalation endpoint. The demo admin may approve its own drafts for academic demonstrations; a production separation-of-duties policy is not yet implemented.

## Tests

From `backend`: `..\.venv\Scripts\python -m pytest tests -q`.

From `frontend`: `npm test`, then `npm run build`. The Playwright specification in `frontend/tests` requires both servers, a seeded demo database, and an installed Playwright Chromium browser. Run `npx playwright install chromium` then `npm run test:e2e` on a development machine. E2E creates and approves a local order; use a disposable demo database.

## Docker and migrations

Set `POSTGRES_PASSWORD` and `JWT_SECRET` in a local `.env` (never commit it), then run `docker compose up --build`. Visit http://localhost:8080. Create the first account with `docker compose exec backend python bootstrap.py --email your@email.example`. Load synthetic data from the app if desired. Docker has separate persistent PostgreSQL storage and an nginx frontend proxy. Docker execution requires Docker Desktop and is not implied by a successful local build.

Run `alembic upgrade head` from `backend` for a new database. The initial migration contains explicit frozen DDL. Future schema changes must add explicit Alembic revisions. SQLite development initializes missing tables automatically; production starts through migrations.

## Scope and remaining production work

This is an academic demonstrator, not a production ERP. Shared analysis workspaces underpin related sidebar entries. Categories and roles use constrained application fields rather than separate normalized lookup tables; sales and POs are single-product records. Warehouse capacity is per-product configured capacity, not volumetric cross-product capacity. No receipt/fulfillment lifecycle or supplier transmission connector is provided. There is no global budget/warehouse portfolio optimization, persistent graph resume, durable job queue, scheduled monitoring, holiday/promotional features, autonomous retry worker, or enforceable hard tool cancellation. Import supports products/sales/inventory, not every entity. User management is read-only; runtime settings are environment controlled. Forecasts need at least 42 contiguous daily records and are not stockout-censoring corrected. Supplier terms are seeded/configured; UI supplier editing is not implemented. Rate limiting is per-process, per-client-IP; use an external gateway for distributed deployment.

See `docs/IMPLEMENTATION_PLAN.md` and `docs/VERIFICATION.md` for phase coverage and actual verification results.
