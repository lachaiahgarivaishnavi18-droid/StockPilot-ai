# Phase handoff

| Phase | Implementation and principal files | What to inspect / test |
|---|---|---|
| 1 | Empty checkout inspected; `IMPLEMENTATION_PLAN.md` | Architecture and sequence |
| 2 | `backend/app/database.py`, `models.py`, `security.py`, `schemas.py`, Alembic revision | Login, analyst restrictions, migration check |
| 3 | `frontend/src/main.tsx`, `navigation.ts`, `styles.css`, `api.ts` | Responsive sidebar, theme, loading/errors, 51 routes |
| 4 | `services.py`, REST routes and product/stock/order forms | Create product, adjust stock with human confirmation, compare suppliers |
| 5 | `imports.py`, `seed.py`, `data/samples` | Load synthetic data; preview/map/validate CSV and JSON; confirm stock replacement; import history |
| 6 | `forecasting.py`, modeling studio | Generate forecast; inspect candidate selection, test metrics and uncertainty |
| 7 | `services.py`, replenishment workspace | Safety stock, reorder point, EOQ and net requirement breakdown |
| 8 | Candidate enumeration optimizer | Set budget to zero to see infeasibility; review pack/capacity/cost constraints |
| 9 | `tools.py`, `agents.py`, agent workspace | Run real graph; open execution row; inspect logged validated tools |
| 10 | Draft/approval endpoints, review UI, audit log | Create draft, confirm review, approve; repeated approval rejected |
| 11 | Assistant provider tool binding and local fallback | Ask demand/order/supplier questions for selected product; inspect evidence |
| 12 | `backend/tests`, frontend tests, Dockerfiles, README | See `VERIFICATION.md` for executed checks and limits |

## Next exact step

While the local servers are running, open http://127.0.0.1:5173 and sign in with the local demo credentials from the README. Go to **Data Import** to preview your own product/sales dataset, or **Demand Forecasting** to use seeded synthetic history.

If restarting later, use this single command from the project root:

```powershell
.\scripts\start.ps1
```

It starts hidden API/frontend processes and writes startup logs in `.logs`. Full first-time installation, separate-terminal commands, and Docker instructions are in README.

This delivery provides the core academic workflow and shared operational views. Remaining production capabilities and deviations from the full master brief are explicitly listed in README, rather than represented as completed features.
