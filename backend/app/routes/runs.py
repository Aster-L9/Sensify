import json
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import (
    AnalysisResult, Event, GroundTruthTelemetry, Run, ScenarioGroundTruth, Segment, Telemetry, User, UserRole,
)
from app.schemas import EventOut, RunCreate, RunStateOut, SegmentStateOut
from app.services import runs as runs_service
from app.services.scoring import alerts_for_run
from app.sim.scenarios import ScenarioError, validate_config

router = APIRouter(prefix="/runs", tags=["runs"])


def get_run_or_404(db: Session, run_id: int) -> Run:
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/")
def list_runs(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    runs = db.query(Run).order_by(Run.started_at.desc()).all()
    for run in runs:
        runs_service.refresh_status(db, run)
    if status:
        runs = [r for r in runs if r.status == status]
    return [runs_service.run_out(r, user) for r in runs[skip:skip + limit]]


@router.get("/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = get_run_or_404(db, run_id)
    runs_service.refresh_status(db, run)
    return runs_service.run_out(run, user)


@router.post("/")
def create_normal_run(data: RunCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    raw = {"scenario_type": "normal", **data.model_dump(exclude={"name", "description"}, exclude_none=True)}
    try:
        cfg = validate_config(raw)
    except ScenarioError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    run = runs_service.launch_run(db, cfg, admin, name=data.name, description=data.description)
    return runs_service.run_out(run, admin)


@router.get("/{run_id}/state", response_model=RunStateOut)
def get_run_state(
    run_id: int,
    at: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = get_run_or_404(db, run_id)
    revealed, status = runs_service.reveal(run)
    tick = runs_service.resolve_tick(run, at)
    rows = (
        db.query(Telemetry, Segment)
        .join(Segment, Telemetry.segment_id == Segment.id)
        .filter(Telemetry.run_id == run_id, Telemetry.tick == tick)
        .order_by(Segment.order_index)
        .all()
    )
    results = {r.segment_id: r for r in db.query(AnalysisResult).filter(
        AnalysisResult.run_id == run_id, AnalysisResult.tick == tick).all()}
    segments = []
    for t, seg in rows:
        res = results.get(seg.id)
        factors = json.loads(res.trust_factors) if res else []
        segments.append(SegmentStateOut(
            segment_id=seg.id, code=seg.code, name=seg.name, segment_type=seg.segment_type,
            pressure_bar=t.pressure_bar, flow_m3h=t.flow_m3h, temperature_c=t.temperature_c,
            valve_open_pct=t.valve_open_pct, pump_speed_pct=t.pump_speed_pct,
            valve_state=t.valve_state, equipment_state=t.equipment_state,
            anomaly_score=res.anomaly_score if res else None, ml_flag=res.ml_flag if res else False,
            trust_score=res.trust_score if res else None, trust_status=res.trust_status if res else None,
            state=res.state if res else "normal", top_factor=factors[0] if factors else None, factors=factors,
        ))
    cutoff = revealed - 1
    open_alerts = sum(1 for a in alerts_for_run(db, run, cutoff) if a["start_tick"] <= tick <= a["end_tick"])
    return RunStateOut(
        run_id=run.id, status=status, tick=tick, revealed_ticks=revealed, duration_ticks=run.duration_ticks,
        timestamp=run.started_at + timedelta(seconds=tick * run.tick_seconds), segments=segments,
        open_alerts=open_alerts,
    )


@router.get("/{run_id}/events", response_model=list[EventOut])
def get_run_events(
    run_id: int,
    category: Optional[str] = None,
    segment_id: Optional[int] = None,
    include_ground_truth: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = get_run_or_404(db, run_id)
    cutoff = runs_service.resolve_tick(run, None)
    query = db.query(Event, Segment).outerjoin(Segment, Event.segment_id == Segment.id).filter(
        Event.run_id == run_id, Event.tick <= cutoff)
    if not (include_ground_truth and user.role == UserRole.admin.value):
        query = query.filter(Event.observable.is_(True))
    if category:
        query = query.filter(Event.category == category)
    if segment_id is not None:
        query = query.filter(Event.segment_id == segment_id)
    return [EventOut(
        id=e.id, run_id=e.run_id, tick=e.tick, timestamp=e.timestamp, segment_id=e.segment_id,
        segment_code=seg.code if seg else None, source=e.source, category=e.category, event_type=e.event_type,
        authorized=e.authorized, severity=e.severity, details=e.details, origin=e.origin, observable=e.observable,
    ) for e, seg in query.order_by(Event.tick, Event.id).all()]


@router.get("/{run_id}/ground-truth")
def get_ground_truth(run_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    run = get_run_or_404(db, run_id)
    cutoff = runs_service.resolve_tick(run, None)
    gt = db.query(ScenarioGroundTruth).filter(ScenarioGroundTruth.run_id == run_id).first()
    segments = db.query(Segment).order_by(Segment.order_index).all()
    code_by_id = {s.id: s.code for s in segments}
    rows = (
        db.query(GroundTruthTelemetry)
        .filter(GroundTruthTelemetry.run_id == run_id, GroundTruthTelemetry.tick <= cutoff)
        .order_by(GroundTruthTelemetry.tick)
        .all()
    )
    per_segment = {s.id: {"segment_id": s.id, "code": s.code, "ticks": [], "phase": [], "process_affected": [],
                          "reporting_compromised": [], "actual_pressure_bar": [], "actual_flow_m3h": [],
                          "actual_temperature_c": []} for s in segments}
    for r in rows:
        seg = per_segment[r.segment_id]
        seg["ticks"].append(r.tick)
        seg["phase"].append(r.phase)
        seg["process_affected"].append(r.process_affected)
        seg["reporting_compromised"].append(r.reporting_compromised)
        seg["actual_pressure_bar"].append(r.actual_pressure_bar)
        seg["actual_flow_m3h"].append(r.actual_flow_m3h)
        seg["actual_temperature_c"].append(r.actual_temperature_c)
    summary = None
    if gt:
        summary = {
            "scenario_type": gt.scenario_type, "method": gt.method,
            "target_segment": code_by_id.get(gt.target_segment_id), "event_start_tick": gt.event_start_tick,
            "event_peak_tick": gt.event_peak_tick, "event_end_tick": gt.event_end_tick,
            "expected_root_cause": gt.expected_root_cause,
            "manipulated_signal_or_asset": gt.manipulated_signal_or_asset, "notes": gt.notes,
        }
    return {"run_id": run.id, "cutoff_tick": cutoff, "summary": summary, "segments": list(per_segment.values())}
