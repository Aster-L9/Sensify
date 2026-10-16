"""
Seed script — populates the database with initial data:
- Default admin user
- 6-segment pipeline topology (Eastern Saudi Arabia)
- 3 sample simulation runs with telemetry
- Activity log entries
"""
import json
import random
import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import (
    User, Segment, Run, Telemetry, ControlEvent,
    SecurityEvent, ActivityLog, UserRole, RunStatus, SegmentState,
)
from app.auth import hash_password
from app.config import required_env


# ── Pipeline Topology (Eastern Saudi Arabia — Dhahran to Jubail) ───────────────
SEGMENTS = [
    {
        "name": "Dhahran Terminal",
        "segment_type": "terminal",
        "lat_start": 26.2361, "lon_start": 50.0393,
        "lat_end": 26.2861, "lon_end": 50.0593,
        "length_km": 5.8, "diameter_inches": 42, "max_pressure_psi": 1400,
        "state": SegmentState.operational.value,
    },
    {
        "name": "Pipeline Corridor A",
        "segment_type": "pipeline",
        "lat_start": 26.2861, "lon_start": 50.0593,
        "lat_end": 26.3900, "lon_end": 50.0800,
        "length_km": 12.3, "diameter_inches": 36, "max_pressure_psi": 1200,
        "state": SegmentState.operational.value,
    },
    {
        "name": "Pump Station Alpha",
        "segment_type": "pump_station",
        "lat_start": 26.3900, "lon_start": 50.0800,
        "lat_end": 26.4200, "lon_end": 50.0950,
        "length_km": 3.5, "diameter_inches": 36, "max_pressure_psi": 1500,
        "state": SegmentState.operational.value,
    },
    {
        "name": "Pipeline Corridor B",
        "segment_type": "pipeline",
        "lat_start": 26.4200, "lon_start": 50.0950,
        "lat_end": 26.5500, "lon_end": 50.1000,
        "length_km": 15.7, "diameter_inches": 36, "max_pressure_psi": 1200,
        "state": SegmentState.warning.value,
    },
    {
        "name": "Valve Station V-12",
        "segment_type": "valve_station",
        "lat_start": 26.5500, "lon_start": 50.1000,
        "lat_end": 26.5800, "lon_end": 50.1050,
        "length_km": 3.4, "diameter_inches": 36, "max_pressure_psi": 1200,
        "state": SegmentState.operational.value,
    },
    {
        "name": "Jubail Industrial Terminal",
        "segment_type": "terminal",
        "lat_start": 26.5800, "lon_start": 50.1050,
        "lat_end": 26.9600, "lon_end": 49.6600,
        "length_km": 48.2, "diameter_inches": 48, "max_pressure_psi": 1400,
        "state": SegmentState.operational.value,
    },
]


def generate_telemetry(run_id: int, segment_id: int, seed: int,
                       start_time: datetime, points: int = 120,
                       interval_minutes: int = 5) -> list:
    """Generate correlated normal-operation telemetry data."""
    rng = random.Random(seed + segment_id * 1000 + run_id)
    data = []

    # Base values per segment
    base_pressure = 950 + rng.random() * 150
    base_flow = 800 + rng.random() * 600
    base_temp = 75 + rng.random() * 30

    for i in range(points):
        ts = start_time + timedelta(minutes=i * interval_minutes)
        # Correlated walk with periodic component
        hour_factor = math.sin(i * math.pi / 24) * 15
        pressure = base_pressure + hour_factor + rng.gauss(0, 8)
        flow = base_flow + hour_factor * 2 + rng.gauss(0, 15)
        temp = base_temp + math.sin(i * math.pi / 48) * 5 + rng.gauss(0, 1.5)

        # Ground truth
        data.append(Telemetry(
            run_id=run_id, segment_id=segment_id, timestamp=ts,
            pressure_psi=round(pressure, 2),
            flow_rate_bph=round(flow, 2),
            temperature_f=round(temp, 2),
            is_ground_truth=True,
        ))
        # Reported (with sensor noise)
        data.append(Telemetry(
            run_id=run_id, segment_id=segment_id, timestamp=ts,
            pressure_psi=round(pressure + rng.gauss(0, 3), 2),
            flow_rate_bph=round(flow + rng.gauss(0, 8), 2),
            temperature_f=round(temp + rng.gauss(0, 0.5), 2),
            is_ground_truth=False,
        ))

    return data


def seed_database(db: Session):
    """Seed the database with initial data if empty."""
    # Check if already seeded
    if db.query(User).first():
        return

    import os
    admin_email = os.getenv("ADMIN_EMAIL", "admin@sensify.local")
    admin_password = required_env("ADMIN_PASSWORD")
    analyst_password = required_env("ANALYST_PASSWORD")
    admin_username = os.getenv("ADMIN_USERNAME", "admin")

    # ── Create admin user ──────────────────────────────────────────────────
    admin = User(
        username=admin_username,
        email=admin_email,
        hashed_password=hash_password(admin_password),
        role=UserRole.admin.value,
        is_active=True,
        created_at=datetime.utcnow() - timedelta(days=30),
    )
    db.add(admin)
    db.flush()

    # Create analyst user
    analyst = User(
        username="analyst",
        email="analyst@sensify.local",
        hashed_password=hash_password(analyst_password),
        role=UserRole.analyst.value,
        is_active=True,
        created_at=datetime.utcnow() - timedelta(days=15),
    )
    db.add(analyst)
    db.flush()

    # ── Create segments ────────────────────────────────────────────────────
    segment_objs = []
    for idx, seg_data in enumerate(SEGMENTS):
        seg = Segment(order_index=idx, **seg_data)
        db.add(seg)
        segment_objs.append(seg)
    db.flush()

    # ── Create runs ────────────────────────────────────────────────────────
    now = datetime.utcnow()
    runs_data = [
        {
            "name": "Normal Operations — Batch 47",
            "description": "Standard throughput monitoring run",
            "status": RunStatus.active.value,
            "created_by": admin.id,
            "created_at": now - timedelta(hours=6),
            "seed": 42,
        },
        {
            "name": "Pressure Test — Corridor B",
            "description": "Elevated pressure test on Pipeline Corridor B",
            "status": RunStatus.completed.value,
            "created_by": admin.id,
            "created_at": now - timedelta(days=2),
            "ended_at": now - timedelta(days=1, hours=18),
            "seed": 123,
        },
        {
            "name": "Flow Calibration Run",
            "description": "Flow sensor calibration across all segments",
            "status": RunStatus.completed.value,
            "created_by": admin.id,
            "created_at": now - timedelta(days=5),
            "ended_at": now - timedelta(days=4, hours=12),
            "seed": 256,
        },
    ]

    run_objs = []
    for run_data in runs_data:
        run = Run(**run_data)
        db.add(run)
        run_objs.append(run)
    db.flush()

    # ── Generate telemetry for each run & segment ──────────────────────────
    for run in run_objs:
        for seg in segment_objs:
            points = 120 if run.status == RunStatus.active.value else 80
            telemetry_data = generate_telemetry(
                run.id, seg.id, run.seed, run.created_at, points
            )
            db.bulk_save_objects(telemetry_data)

    # ── Control events ─────────────────────────────────────────────────────
    control_events = [
        ControlEvent(
            run_id=run_objs[0].id, segment_id=segment_objs[4].id,
            timestamp=now - timedelta(hours=3),
            event_type="valve_open", valve_state="open",
            details="Routine valve check — V-12 opened"
        ),
        ControlEvent(
            run_id=run_objs[0].id, segment_id=segment_objs[2].id,
            timestamp=now - timedelta(hours=5),
            event_type="pump_start", valve_state=None,
            details="Pump Station Alpha — primary pump engaged"
        ),
    ]
    db.bulk_save_objects(control_events)

    # ── Activity log ───────────────────────────────────────────────────────
    activities = [
        ActivityLog(
            user_id=admin.id, action="login",
            entity_type=None, entity_id=None,
            timestamp=now - timedelta(hours=6),
            details="Admin login from 10.0.1.50"
        ),
        ActivityLog(
            user_id=admin.id, action="run_created",
            entity_type="run", entity_id=run_objs[0].id,
            timestamp=now - timedelta(hours=6),
            details=f"Created run: {run_objs[0].name}"
        ),
        ActivityLog(
            user_id=admin.id, action="run_created",
            entity_type="run", entity_id=run_objs[1].id,
            timestamp=now - timedelta(days=2),
            details=f"Created run: {run_objs[1].name}"
        ),
        ActivityLog(
            user_id=admin.id, action="run_completed",
            entity_type="run", entity_id=run_objs[1].id,
            timestamp=now - timedelta(days=1, hours=18),
            details=f"Run completed: {run_objs[1].name}"
        ),
        ActivityLog(
            user_id=analyst.id, action="login",
            entity_type=None, entity_id=None,
            timestamp=now - timedelta(hours=2),
            details="Analyst login from 10.0.1.55"
        ),
    ]
    db.bulk_save_objects(activities)

    db.commit()
    print("Database seeded successfully")
    print(f"  Admin account created: {admin_email}")
    print("  Analyst account created: analyst@sensify.local")
    print(f"  {len(segment_objs)} segments, {len(run_objs)} runs created")
