"""Dashboard summary: run counts, live values, anomaly/trust alerts and detection rate."""
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import AnalysisResult, Run, RunStatus, ScenarioGroundTruth, Telemetry, User, UserRole
from app.routes.alerts import collect_alerts
from app.services import runs as runs_service
from app.services.runs import resolve_tick, run_out
from app.services.scoring import ordered_segments

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

STATES = ("normal", "anomalous", "low_trust")
GRACE_TICKS = 12


def _live_block(db: Session, run: Run) -> dict:
    tick = resolve_tick(run, None)
    segments = ordered_segments(db)
    rows = {t.segment_id: t for t in db.query(Telemetry).filter(Telemetry.run_id == run.id, Telemetry.tick == tick)}
    results = {r.segment_id: r for r in db.query(AnalysisResult).filter(
        AnalysisResult.run_id == run.id, AnalysisResult.tick == tick)}
    by_state = {s: 0 for s in STATES}
    trust_alerts = []
    for seg in segments:
        res = results.get(seg.id)
        state = res.state if res else "normal"
        by_state[state] = by_state.get(state, 0) + 1
        if res and res.trust_status != "Supported":
            import json
            factors = json.loads(res.trust_factors or "[]")
            trust_alerts.append({"run_id": run.id, "segment_id": seg.id, "code": seg.code, "name": seg.name,
                                 "trust_score": res.trust_score, "trust_status": res.trust_status,
                                 "top_factor": factors[0] if factors else None})
    pressures = [rows[s.id].pressure_bar for s in segments if s.id in rows]
    first = rows.get(segments[0].id) if segments else None
    return {
        "run_id": run.id, "run_name": run.name, "tick": tick,
        "avg_pressure_bar": round(sum(pressures) / len(pressures), 2) if pressures else None,
        "throughput_m3h": round(first.flow_m3h, 1) if first else None,
        "segments_by_state": by_state, "trust_alerts": trust_alerts,
    }


def _detection(db: Session, runs: list[Run], alerts: list[dict]) -> dict:
    truth = {g.run_id: g for g in db.query(ScenarioGroundTruth).all()}
    detected = total = 0
    for run in runs:
        gt = truth.get(run.id)
        # Completed runs only: counting a live run the moment its event starts would tell analysts
        # that (and when) something was injected, and they investigate live runs blind.
        if not gt or gt.scenario_type == "normal" or gt.event_start_tick is None or run.status != RunStatus.completed.value:
            continue
        cutoff = resolve_tick(run, None)
        total += 1
        end = min(gt.event_end_tick + GRACE_TICKS, cutoff)
        detected += any(a["run_id"] == run.id and a["start_tick"] <= end and a["end_tick"] >= gt.event_start_tick
                        for a in alerts)
    return {"detected": detected, "total": total, "rate": round(detected / total, 4) if total else None}


def _runs_flagged(runs: list[Run], alerts: list[dict]) -> dict:
    """Completed runs with at least one flagged window: built from alerts only, so safe for every role."""
    completed = [r for r in runs if r.status == RunStatus.completed.value]
    with_alerts = {a["run_id"] for a in alerts}
    return {"flagged": sum(r.id in with_alerts for r in completed), "completed": len(completed)}


@router.get("/summary")
def get_dashboard_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    now = runs_service.utcnow()
    runs = db.query(Run).order_by(Run.started_at.desc(), Run.id.desc()).all()
    alerts = collect_alerts(db, runs)  # also refreshes run statuses
    started = [r for r in runs if r.started_at <= now]  # a run scheduled in the future is not the active run
    active = next((r for r in started if r.status == RunStatus.active.value), None)
    live_run = active or next((r for r in started if r.status == RunStatus.completed.value), None)
    live = _live_block(db, live_run) if live_run else None

    run_start = {r.id: r.started_at for r in runs}
    recent = [a for a in alerts if run_start[a["run_id"]] >= now - timedelta(hours=24)]
    days = [(now - timedelta(days=d)).date() for d in range(13, -1, -1)]
    per_day = {d: {"date": d.isoformat(), "anomaly": 0, "low_trust": 0} for d in days}
    for a in alerts:
        day = a["start_time"].date()
        if day in per_day:
            for kind in a["kinds"]:
                per_day[day][kind] += 1

    states = (live or {}).get("segments_by_state", {})
    if states.get("low_trust"):
        system_status = "critical"
    elif states.get("anomalous"):
        system_status = "warning"
    elif active:
        system_status = "operational"
    else:
        system_status = "idle"

    recent_trust = [a for a in alerts if "low_trust" in a["kinds"]][:5]
    return {
        "total_runs": len(runs),
        "active_runs": sum(r.status == RunStatus.active.value for r in runs),
        "completed_runs": sum(r.status == RunStatus.completed.value for r in runs),
        "total_segments": len(ordered_segments(db)),
        "segments_by_state": states,
        "system_status": system_status,
        "latest_run": run_out(runs[0], user) if runs else None,
        "telemetry_points": db.query(func.count(Telemetry.id)).scalar(),
        "active_run": run_out(active, user) if active else None,
        "live": live,
        "anomaly_count_24h": sum("anomaly" in a["kinds"] for a in recent),
        "anomaly_count_total": sum("anomaly" in a["kinds"] for a in alerts),
        # Detection needs ground truth (which runs carried a scenario), so it is for administrators only.
        "detection": _detection(db, runs, alerts) if user.role == UserRole.admin.value else None,
        "runs_flagged": _runs_flagged(runs, alerts),
        "trust_alerts": (live or {}).get("trust_alerts", []),
        "recent_trust_alerts": recent_trust,
        "alerts_per_day": list(per_day.values()),
    }
