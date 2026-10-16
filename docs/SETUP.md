# Run the Sprint 2 application locally

Sensify is an academic development prototype with a Next.js 14 / React frontend and a FastAPI / SQLAlchemy backend. Start with a fresh local database when setting up this source snapshot. The original archive and any existing local database remain independent of this checkout.

## Prerequisites

- Python 3.12 (the version used for verification), with venv and pip.
- Node.js 20 or newer, with npm (verification uses Node.js 24).
- Git and access to the private repository.

## Backend and first model

From the repository root:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

On Windows, create the environment with `py -3.12 -m venv .venv`, then activate it with `.venv\Scripts\Activate.ps1` in PowerShell.

Edit `backend/.env` before continuing:

- Set `JWT_SECRET` to a unique random value. Generate one locally with `python -c "import secrets; print(secrets.token_hex(32))"`.
- Set `ADMIN_PASSWORD` and `ANALYST_PASSWORD` to separate passwords of your choosing (at least six characters).
- Keep `ADMIN_EMAIL=admin@sensify.local` for the frontend's Administrator selector. The Analyst selector accepts an email address.
- Leave `SEED_DEMO_RUNS=1` for six example scenarios, or set it to `0` for an empty run list.

Secrets have no committed defaults. Keep real environment files and account details local.

With the virtual environment active:

```sh
cd backend
python -m ml.train --generate --activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The training command generates the default simulated dataset in `backend/ml/data/`, writes the next trained version to `backend/model_store/vN/`, evaluates it, and registers/activates it in the local SQLite database. This extra first-run step replaces the archive's prebuilt model and database. Start the API after training so seeded demo runs are scored with the active model.

The API creates tables, users, the six-segment topology and optional demo runs. Administrator login uses `admin@sensify.local` and your configured `ADMIN_PASSWORD`; Analyst login uses `analyst@sensify.local` and your configured `ANALYST_PASSWORD`. Password settings apply when creating users in an empty database; changing the environment does not reset an existing account.

The API can start without a model, but runs then have no ML scores. An Administrator can train from the Models page and press **Set active**; existing runs can then be re-analyzed. For CLI training options and evaluation limitations, see [the model guide](../backend/ml/README.md).

- API health: http://localhost:8000/health
- Interactive API documentation: http://localhost:8000/docs

## Frontend

In a second terminal, from the repository root:

```sh
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

Open http://localhost:3000. `NEXT_PUBLIC_API_URL` defaults to http://localhost:8000 and must point to the backend. Browser-visible `NEXT_PUBLIC_` settings must not contain secrets.

For a production-mode local build, use `npm run build`, then `npm start`. This is a build check, not a production deployment configuration.

## Automated checks

From the repository root, with the Python environment active:

```sh
python -m pip install -r backend/requirements-dev.txt
cd backend
python -m pytest
```

Tests isolate the database, credentials, datasets and model artifacts in temporary directories. They exercise simulation, scenarios, feature generation, training, detection, trust, migration, API access and configuration validation. The supplied evaluation snapshot also supports a report-formatting regression check.

From `frontend/`:

```sh
npm ci
npm run lint
npm run build
```

## What belongs in Git

Commit source code, required image assets, tests, dependency manifests/lockfiles, shared configuration, blank environment templates and documentation. The supplied evaluation JSON/Markdown is retained under `docs/evaluation/sprint-2-v1/` as reference evidence.

Installed dependencies, build output, caches, local databases, real `.env` files, credential documents, generated training CSVs and serialized models remain local. `.gitignore` covers these paths. Regenerate data and models through the versioned source rather than copying the old database or serialized model into Git.
