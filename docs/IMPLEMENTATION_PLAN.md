# StockPilot AI implementation plan

Repository inspection: the checkout contained only Git metadata. No source, dependencies, database, or existing application was present.

## Architecture

React + TypeScript + Vite → authenticated FastAPI REST API → SQLAlchemy relational database (SQLite locally; PostgreSQL via DATABASE_URL). Forecasts use chronological model selection and a separate test period. Inventory calculations and constrained candidate optimization are deterministic application services. LangGraph coordinates validated application tools; optional OpenAI-compatible tool calling uses the same registry. Purchase orders remain local records and require an authenticated approver. No supplier transmission integration is configured.

## Phases and verification

1. Inspect repository, document architecture and scope.
2. Database, migrations, password hashing, JWT and roles; verify authentication and persistence.
3. Responsive frontend shell, routing and API integration; compile production bundle.
4. Products, stock, suppliers, purchase orders; verify mutations and approval transitions.
5. Transactional CSV/JSON import with preview, mapping and history; verify invalid imports roll back.
6. Forecast candidates, chronological validation/test metrics and intervals; verify no future observations enter training.
7. Safety stock, reorder point, EOQ and net requirement; verify units and constraints.
8. Feasible order candidate optimization; verify capacity, MOQ, pack size and budget constraints.
9. Typed LangGraph nodes, registry schemas, tool authorization, invocation logs and checkpoints; verify real execution traces.
10. Authenticated human approvals and audit history; verify agents cannot approve.
11. Grounded assistant with explicitly labeled deterministic fallback and optional provider configuration.
12. API/domain tests, frontend build and critical workflow checks; document deployment and remaining limitations.

The 51 sidebar destinations use shared operational views, scoped to the requested analysis; avoid duplicating calculations across pages. Every metric is database-derived. Synthetic seed data and local assistant mode are labeled.
