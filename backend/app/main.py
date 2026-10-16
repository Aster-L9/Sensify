import os
from pathlib import Path
from contextlib import asynccontextmanager

from dotenv import load_dotenv

# Load .env before anything else
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import engine, SessionLocal, Base
from app.migrate import migrate_if_needed
from app.seed import seed_database
from app.services.registry import fail_interrupted_training

from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from app.routes.topology import router as topology_router
from app.routes.runs import router as runs_router
from app.routes.telemetry import router as telemetry_router
from app.routes.dashboard import router as dashboard_router
from app.routes.activity import router as activity_router
from app.routes.scenarios import router as scenarios_router
from app.routes.run_analysis import router as run_analysis_router
from app.routes.ml_models import router as ml_models_router
from app.routes.alerts import router as alerts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ────────────────────────────────────────────────────────────
    # Bring the database to the current schema (keeps user accounts), then seed
    migrate_if_needed(engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        fail_interrupted_training(db)
        seed_database(db)
    finally:
        db.close()

    yield


app = FastAPI(
    title="Sensify Pipeline Intelligence API",
    description="Pipeline monitoring and simulation platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(topology_router)
app.include_router(runs_router)
app.include_router(telemetry_router)
app.include_router(dashboard_router)
app.include_router(activity_router)
app.include_router(scenarios_router)
app.include_router(run_analysis_router)
app.include_router(ml_models_router)
app.include_router(alerts_router)


@app.get("/")
async def root():
    return {
        "name": "Sensify Pipeline Intelligence API",
        "version": "1.0.0",
        "status": "operational",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
