# Vercel deployment

Production URL: https://stockpilot-ai-black.vercel.app

Vercel project: `resume-project3/stockpilot-ai`. Database: `stockpilot-db` (Neon Free). Deployment is linked through the official CLI. Project source is maintained at https://github.com/lachaiahgarivaishnavi18-droid/StockPilot-ai.

StockPilot is configured as one FastAPI Vercel project. FastAPI serves the `/api` endpoints and registers the compiled React build through `app.frontend()`, including SPA deep-link fallback. All browser API requests remain same-origin.

## Deployment files

- `app.py`: Vercel entrypoint and React frontend registration.
- `pyproject.toml`: Python 3.12, cloud runtime dependencies, static CDN settings. Vercel prioritizes these dependencies over `requirements.txt` when both exist.
- `vercel.json`: framework, build command and function exclusions/duration.
- `scripts/vercel-build.mjs`: build React and run database migrations.
- `scripts/prepare_vercel.py`: create `.deployment` with source only, excluding local databases, logs, tests, caches and credentials.
- `backend/deploy_init.py`: normalize the PostgreSQL connection URL and apply Alembic migrations during deployment.

## Database and secrets

The Vercel project uses a dedicated Neon PostgreSQL resource on the verified `free_v3` plan. No local SQLite database or local user account is uploaded. Production and preview currently connect to the same dedicated resource: previews must be treated as accessing production records until separate preview branching is configured.

The integration supplies `DATABASE_URL`. `APP_ENV`, `JWT_SECRET`, and `BOOTSTRAP_TOKEN` are encrypted environment variables. The app refuses SQLite and missing JWT secrets when Vercel is detected. Never commit or publish `.vercel-auth`, `.env.local`, or the contents of the cloud environment variables.

The first administrator uses the private one-time setup link supplied at deployment. The user chooses their email and password directly in the application. The bootstrap endpoint checks a high-entropy setup token and refuses to create another administrator after setup completes. PostgreSQL serializes competing setup attempts with a transaction advisory lock. Normal public registration always creates an analyst account. No public demo administrator is provisioned in the cloud.

After setup, load synthetic data using **Load sample data**, or import the user's own datasets. Local accounts and records remain on the local computer.

## Redeploy

From the project root, run `python scripts/prepare_vercel.py`, then deploy from `.deployment` using the official Vercel CLI with the linked account. Keep the existing project identity and environment variables. The initial cloud-secret configuration script is a provisioning helper, not a routine redeploy step; do not rerun it to rotate secrets unintentionally.

The Vercel account connection is local CLI state in ignored `.vercel-auth`. The GitHub remote stores the project source; automatic commit-based Vercel deployment has not been configured.
