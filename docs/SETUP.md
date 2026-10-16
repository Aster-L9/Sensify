# Run the Sprint 1 application locally

The application contains a Next.js 14 / React frontend and a FastAPI / SQLAlchemy backend. SQLite data is generated locally on first backend startup. This is an academic development prototype; these instructions do not constitute a production deployment configuration.

## Prerequisites

- Python 3.10 or newer, with venv and pip.
- A maintained Node.js LTS version that supports Next.js 14, with npm.
- Git, and access to this private repository.

## Backend

From the repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
```

On Windows, activate the environment with `.venv\Scripts\Activate.ps1` in PowerShell.

Edit `backend/.env` before starting the server:

- Set `JWT_SECRET` to a unique, randomly generated secret. Generate one locally with `python -c "import secrets; print(secrets.token_hex(32))"`.
- Set `ADMIN_PASSWORD` and `ANALYST_PASSWORD` to separate passwords of your choosing.
- Adjust the administrator email and username if needed.

These values deliberately have no committed defaults. Keep them local and do not paste them into issues, pull requests, or source files.

```sh
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend creates `database/dummy.db`, the database tables, and sample users, topology, runs, and telemetry on first startup. Login uses `ADMIN_EMAIL` with `ADMIN_PASSWORD`, or `analyst@sensify.local` with `ANALYST_PASSWORD`. Password settings apply when seeding an empty database; changing them does not reset existing users.

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

Open http://localhost:3000. `NEXT_PUBLIC_API_URL` defaults to http://localhost:8000 and must point to the backend. Values beginning with `NEXT_PUBLIC_` are visible in the browser and must not contain secrets.

Next.js regenerates `.next/`, `next-env.d.ts`, and TypeScript build information locally. Do not commit them.

## Configuration tests

From the repository root:

```sh
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v
```

These tests check secret-setting validation. They do not replace a full frontend build, API integration checks, or the charter's acceptance evaluation.

## Repository contents

Commit application source, required images, dependency manifests and lockfiles, shared tool configuration, example environment files, tests, and documentation. Preserve the existing license notice.

Do not commit installed dependencies, build output, caches, local databases, credentials documents, real environment files, IDE preferences, or operating-system metadata. The repository's `.gitignore` covers these files.

The initial source import intentionally excludes the source folder's old `.git` history, one-off editing/database utility scripts, and unreferenced image files. The existing project README and Scrum board remain the planning baseline; importing this version does not mark any user story complete.
