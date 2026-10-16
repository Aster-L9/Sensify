"""
Run service: launch a scenario run (simulate + store), and reveal it over time.

A run is simulated in full at launch, then revealed at playback speed:
every read clamps to the ticks revealed so far.
"""
import json
import math
from datetime import datetime, timedelta

import numpy as np
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.models import (
    ActivityLog, Event, GroundTruthTelemetry, Run, RunStatus, ScenarioGroundTruth, Segment,
    Telemetry, User, UserRole,
)
from app.sim.engine import RunData, simulate_run
from app.sim.scenarios import ScenarioConfig
from app.sim.topology import TICK_SECONDS

ADMIN_ONLY_FIELDS = ("scenario_type", "method", "target_segment", "scenario_params")


def utcnow() -> datetime:
    return datetime.utcnow()


def reveal(run: Run, now: datetime | None = None) -> tuple[int, str]:
    """(revealed_ticks, status) for a run at wall-clock time `now`."""
    now = now or utcnow()
    elapsed = max((now - run.started_at).total_seconds(), 0.0)
    revealed = min(run.duration_ticks, math.floor(elapsed * run.playback_speed / run.tick_seconds) + 1)
    status = RunStatus.completed.value if revealed >= run.duration_ticks else RunStatus.active.value
    return revealed, status


def refresh_status(db: Session, run: Run) -> None:
    _, status = reveal(run)
    if status != run.status:
        run.status = status
        if status == RunStatus.completed.value:
            playback = run.duration_ticks * run.tick_seconds / run.playback_speed
            run.ended_at = run.started_at + timedelta(seconds=playback)
        db.commit()


def resolve_tick(run: Run, at: int | None, now: datetime | None = None) -> int:
    """Clamp a requested tick to the revealed range; default to the latest revealed tick."""
    revealed, _ = reveal(run, now)
    last = revealed - 1
    return last if at is None else max(0, min(int(at), last))


def scoring_hook(db: Session, run: Run) -> None:
    """Score a freshly launched run with the active model (no-op when no model is active)."""
    from app.services.scoring import score_run

    score_run(db, run)


def _none_if_nan(value: float) -> float | None:
    return None if value is None or np.isnan(value) else float(value)


def _store(db: Session, run: Run, data: RunData, seg_ids: list[int]) -> None:
    stamps = [run.started_at + timedelta(seconds=t * TICK_SECONDS) for t in range(data.n_ticks)]
    rep, act = data.reported, data.actual
    telemetry, truth = [], []
    for t in range(data.n_ticks):
        for i, seg_id in enumerate(seg_ids):
            telemetry.append({
                "run_id": run.id, "segment_id": seg_id, "tick": t, "timestamp": stamps[t],
                "pressure_bar": float(rep["pressure"][t, i]), "flow_m3h": float(rep["flow"][t, i]),
                "temperature_c": float(rep["temperature"][t, i]),
                "valve_open_pct": _none_if_nan(rep["valve_open"][t, i]),
                "pump_speed_pct": _none_if_nan(rep["pump_speed"][t, i]),
                "valve_state": str(data.valve_state[t, i]), "equipment_state": str(data.equipment_state[t, i]),
            })
            truth.append({
                "run_id": run.id, "segment_id": seg_id, "tick": t, "timestamp": stamps[t],
                "actual_pressure_bar": float(act["pressure"][t, i]), "actual_flow_m3h": float(act["flow"][t, i]),
                "actual_temperature_c": float(act["temperature"][t, i]),
                "actual_valve_open_pct": _none_if_nan(act["valve_open"][t, i]),
                "actual_pump_speed_pct": _none_if_nan(act["pump_speed"][t, i]),
                "phase": str(data.phase[t]), "is_target": bool(data.is_target[i]),
                "process_affected": bool(data.process_affected[t, i]),
                "reporting_compromised": bool(data.reporting_compromised[t, i]),
            })
    db.execute(insert(Telemetry), telemetry)
    db.execute(insert(GroundTruthTelemetry), truth)

    code_to_id = dict(zip(data.segment_codes, seg_ids))
    events = [{
        "run_id": run.id, "segment_id": code_to_id.get(e.segment), "tick": e.tick, "timestamp": stamps[e.tick],
        "source": e.source, "category": e.category, "event_type": e.event_type, "authorized": e.authorized,
        "severity": e.severity, "details": e.details, "observable": e.observable, "origin": "simulator",
    } for e in data.events]
    if events:
        db.execute(insert(Event), events)

    s = data.summary
    db.add(ScenarioGroundTruth(
        run_id=run.id, scenario_type=s.scenario_type, method=s.method,
        target_segment_id=code_to_id.get(s.target_segment), event_start_tick=s.event_start_tick,
        event_peak_tick=s.event_peak_tick, event_end_tick=s.event_end_tick,
        expected_root_cause=s.expected_root_cause, manipulated_signal_or_asset=s.manipulated_signal_or_asset,
        notes=s.notes,
    ))


def launch_run(db: Session, cfg: ScenarioConfig, user: User | None, name: str | None = None,
               description: str | None = None, started_at: datetime | None = None, score: bool = True) -> Run:
    data = simulate_run(cfg)
    segments = db.query(Segment).order_by(Segment.order_index).all()
    seg_ids = [s.id for s in segments]
    target_id = next((s.id for s in segments if s.code == cfg.target_segment), None)

    run = Run(
        name=name or "pending", description=description, scenario_type=cfg.scenario_type, method=cfg.method,
        target_segment_id=target_id, scenario_params=json.dumps(cfg.to_params()), seed=cfg.seed,
        tick_seconds=TICK_SECONDS, duration_ticks=cfg.duration_ticks, playback_speed=cfg.playback_speed,
        started_at=started_at or utcnow(), status=RunStatus.active.value,
        created_by=user.id if user else None, created_at=utcnow(),
    )
    db.add(run)
    db.flush()
    if not name:
        run.name = f"Run {run.id:04d}"
    _store(db, run, data, seg_ids)
    db.add(ActivityLog(
        user_id=user.id if user else None, action="scenario_launched", entity_type="run", entity_id=run.id,
        details=f"Launched run: {run.name}", timestamp=utcnow(),
    ))
    db.commit()
    db.refresh(run)
    refresh_status(db, run)
    if score:
        scoring_hook(db, run)
    return run


def run_out(run: Run, user: User, now: datetime | None = None) -> dict:
    """Public view of a run. Scenario (ground-truth) fields are included for admins only."""
    revealed, status = reveal(run, now)
    out = {
        "id": run.id, "name": run.name, "description": run.description, "status": status,
        "created_by": run.created_by, "creator_username": run.creator.username if run.creator else None,
        "created_at": run.created_at, "started_at": run.started_at, "ended_at": run.ended_at,
        "tick_seconds": run.tick_seconds, "duration_ticks": run.duration_ticks,
        "playback_speed": run.playback_speed, "revealed_ticks": revealed,
        "progress": round(revealed / run.duration_ticks, 4),
        "scored": run.model_version_id is not None,
        "model_version": run.model_version.version if run.model_version else None,
    }
    if user.role == UserRole.admin.value:
        # The seed reproduces the run without its injection, so it is ground truth too.
        out.update({
            "seed": run.seed, "scenario_type": run.scenario_type, "method": run.method,
            "target_segment": run.target_segment.code if run.target_segment else None,
            "scenario_params": json.loads(run.scenario_params or "{}"),
        })
    return out
