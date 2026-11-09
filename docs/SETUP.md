# Run Sensify locally

Sensify is an academic development prototype with a Next.js 14 / React frontend and a FastAPI / SQLAlchemy backend. It runs on one machine: the API on port 8000, the web application on port 3000, and a local SQLite database. These steps start from a fresh database; nothing generated is committed to Git.

## Prerequisites

- Python 3.12 to 3.14, with venv and pip.
- Node.js 20 or newer, with npm.
- Windows 10/11 or macOS 12 or newer (the scientific Python packages publish wheels for these).
- Git.

## Backend and first model

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

On Windows, create the environment with `py -3.12 -m venv .venv`, then activate it with `.venv\Scripts\Activate.ps1` in PowerShell. If PowerShell reports that running scripts is disabled, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in the same window first.

Edit `backend/.env` before continuing:

- Set `JWT_SECRET` to a unique random value. Generate one locally with `python -c "import secrets; print(secrets.token_hex(32))"`.
- Set `ADMIN_PASSWORD` and `ANALYST_PASSWORD` to separate passwords of your choosing (at least six characters).
- Keep `ADMIN_EMAIL=admin@sensify.local` for the frontend's Administrator selector. The Analyst selector accepts an email address.
- Leave `SEED_DEMO_RUNS=1` for six example scenarios, or set it to `0` for an empty run list.

Secrets have no committed defaults, and the API refuses to start without them. Keep real environment files and account details local.

With the virtual environment active:

```sh
cd backend
python -m ml.train --generate --activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The training command generates the simulated dataset in `backend/ml/data/`, writes the next trained version to `backend/model_store/vN/`, evaluates it, and registers and activates it in the local SQLite database. It takes about half a minute. Start the API after training so the seeded demo runs are scored with the active model. Add `--reload` to the `uvicorn` command for development on macOS or Linux; it can hang on Windows.

On first start the API creates the tables, the six-segment topology, the two seeded accounts, the optional demo runs and the archived evaluation (e1), so the Incidents and Evaluation pages have content straight away. Administrator login uses `admin@sensify.local` and your `ADMIN_PASSWORD`; Analyst login uses `analyst@sensify.local` and your `ANALYST_PASSWORD`. Password settings apply only when users are created in an empty database; changing the environment later does not reset an existing account. New analysts can also register from the **Sign Up** page.

- API health: http://localhost:8000/health
- Interactive API documentation: http://localhost:8000/docs

### Existing local database

The database schema is version 4. A Sprint 2 or Sprint 3 database is upgraded in place on first start, keeping runs, analysis results and users. A Sprint 1 database is rebuilt: accounts and passwords are kept, the old demo runs are replaced, and a copy of the old file is saved as `database/dummy.db.sprint1.bak` (ignored by Git).

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

## What to try

As the Administrator:

1. Open **Scenario Builder**, choose **Telemetry manipulation**, select SEG-03 on the line, set the onset to 2 min and the speed to 20x, then press **Launch and watch**.
2. Open **Pipeline Map** or **Dashboard**. After the onset, SEG-03 is shown as low trust (dashed line and shield badge).
3. On the **Dashboard**, press **Start demo** and follow the demo guide.
4. Open **Incidents**, then an incident. Review its classification, evidence, timeline, attack-to-impact chain and MITRE ATT&CK for ICS context, and download the PDF or CSV report.
5. Open **Evaluation** to compare threshold-only, ML-only and the full hybrid approach on development and held-out data. Administrators can start a new evaluation; it takes several minutes.
6. **Models** shows how the detection model performs and trains new versions.

As the Analyst (in another browser, or after signing out):

- The same run plays on the dashboard and map, and flagged windows appear under **Alerts**. Analysts never see which scenario was launched and cannot open Scenario Builder or Models.
- **Incidents** lists the investigation results with their evidence. Analysts can resolve and reopen incidents.
- **Evaluation** is read-only for Analysts.

## Data, models and evaluations

From `backend/` with the virtual environment active:

```sh
python -m ml.generate_dataset           # rebuild the development dataset (seed 2026)
python -m ml.train --activate           # train, grade and activate a new model version
python -m ml.generate_heldout           # rebuild the frozen held-out set (seed 4242)
python -m ml.tune_engine                # tune the investigation engine on the validation split
python -m ml.evaluate --dataset both    # write a new backend/evaluations/eN
```

The held-out set in `backend/ml/heldout/` and the recorded evaluations in `backend/evaluations/` are committed as evidence. The held-out labels are not changed after the first evaluation, and the investigation engine is never tuned on them. `python -m ml.tune_engine --write-snapshot` changes the engine freeze snapshot and requires a new engine version. For CLI options and limitations, see [the model guide](../backend/ml/README.md).

## Automated checks

From the repository root, with the Python environment active:

```sh
python -m pip install -r backend/requirements-dev.txt
cd backend
python -m pytest
```

Tests isolate the database, credentials, datasets and model artifacts in temporary directories. They cover simulation, scenarios, feature generation, training, detection, trust, the investigation engine and its freeze snapshot, incidents, reports, evaluation, migration, API access rules and configuration validation.

From `frontend/`:

```sh
npm ci
npm run lint
npm run build
```

## Troubleshooting

- **`pip install` fails while building a package such as `pydantic-core`:** check that Python is 3.12 or newer. If the virtual environment was created with an older Python, delete it and create it again.
- **`uvicorn` is not found:** the virtual environment is not active.
- **The API stops with "`JWT_SECRET` must be configured":** `backend/.env` is missing or a required secret is blank. Copy `backend/.env.example` and fill in the three secrets.
- **"(trapped) error reading bcrypt version" on the first login:** a harmless warning from the password library; login and signup still work.
- **Login fails with a network error:** the backend is not running, or `NEXT_PUBLIC_API_URL` does not point to it.
- **A run shows "Unscored":** no model was active when the run was launched. As the Administrator, open **Models** and press **Set active** on a ready version, then open the run and press **Re-score with active model**.
- **Port 3000 or 8000 is already in use:** another copy is still running; stop it with Ctrl+C.

## What belongs in Git

Commit source code, required assets (including the bundled DejaVu fonts used by PDF reports), tests and their snapshots, dependency manifests and lockfiles, shared configuration, blank environment templates, documentation, the frozen held-out set and recorded evaluation results. The Sprint 2 evaluation snapshot is archived under `docs/evaluation/sprint-2-v1/`.

Installed dependencies, build output, caches, local databases and their backups, real `.env` files, credential documents, the generated development dataset and serialized models remain local. `.gitignore` covers these paths. Regenerate data and models with the commands above rather than copying a database or model file into Git.
