"""
Seed data: the pipeline segments (from the topology config), the default
accounts, and a set of demo runs.
"""
import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.config import required_env
from app.models import Run, Segment, User, UserRole
from app.sim.topology import SEGMENTS


def _seed_segments(db: Session) -> None:
    if db.query(Segment).first():
        return
    for spec in SEGMENTS:
        db.add(Segment(
            code=spec.code, name=spec.name, segment_type=spec.segment_type, order_index=spec.order,
            lat_start=spec.lat_start, lon_start=spec.lon_start, lat_end=spec.lat_end, lon_end=spec.lon_end,
            length_km=spec.length_km, diameter_mm=spec.diameter_mm,
            design_pressure_bar=spec.design_pressure_bar, equipment=spec.equipment,
        ))
    db.commit()


def _seed_users(db: Session) -> None:
    if db.query(User).first():
        return
    admin_password = required_env("ADMIN_PASSWORD")
    analyst_password = required_env("ANALYST_PASSWORD")
    db.add(User(
        username=os.getenv("ADMIN_USERNAME", "admin"),
        email=os.getenv("ADMIN_EMAIL", "admin@sensify.local"),
        hashed_password=hash_password(admin_password),
        role=UserRole.admin.value, is_active=True,
        created_at=datetime.utcnow() - timedelta(days=30),
    ))
    db.add(User(
        username="analyst", email="analyst@sensify.local",
        hashed_password=hash_password(analyst_password),
        role=UserRole.analyst.value, is_active=True,
        created_at=datetime.utcnow() - timedelta(days=15),
    ))
    db.commit()


# One completed demo run per scenario type, so dashboards and alerts have content on first start.
DEMO_RUNS = [
    ({"scenario_type": "normal", "seed": 101}, timedelta(days=5)),
    ({"scenario_type": "physical_anomaly", "method": "leak", "target_segment": "SEG-04", "magnitude": 0.7, "seed": 102}, timedelta(days=4)),
    ({"scenario_type": "sensor_fault", "method": "erratic", "target_segment": "SEG-02", "magnitude": 0.7, "seed": 103}, timedelta(days=3)),
    ({"scenario_type": "telemetry_manipulation", "method": "replay", "target_segment": "SEG-03", "magnitude": 0.8, "seed": 104}, timedelta(days=2)),
    ({"scenario_type": "unauthorized_control", "method": "valve_close", "target_segment": "SEG-05", "magnitude": 0.9, "seed": 105}, timedelta(days=1)),
    ({"scenario_type": "concealed_physical_incident", "method": "leak", "target_segment": "SEG-04", "magnitude": 0.8, "seed": 106}, timedelta(hours=20)),
]


def seed_demo_runs(db: Session) -> None:
    from app.services import runs as runs_service
    from app.sim.scenarios import validate_config

    if db.query(Run).first():
        return
    admin = db.query(User).filter(User.role == UserRole.admin.value).first()
    for raw, ago in DEMO_RUNS:
        runs_service.launch_run(db, validate_config(raw), admin, started_at=runs_service.utcnow() - ago)


def seed_database(db: Session) -> None:
    from app.services.registry import ensure_seed_model

    _seed_segments(db)
    _seed_users(db)
    ensure_seed_model(db)
    if os.getenv("SEED_DEMO_RUNS", "1") == "1":
        seed_demo_runs(db)
