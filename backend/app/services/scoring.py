"""
Scoring service: run the analysis on a stored run and persist the results.

The analysis reads only the reported telemetry table and observable simulator
events. Results for runs still playing are read back no further than the reveal
cutoff; alerts for those runs are rebuilt from the per-tick results so a window
never shows ticks that have not been revealed.
"""
import json
from datetime import timedelta

import numpy as np
from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from app.analysis.consistency import CHECKS
from app.analysis.frame import ObservableEvent, ReportedRun
from app.analysis.model import DetectorModel
from app.analysis.pipeline import analyze_run
from app.analysis.trust import TrustResult, trust_factors
from app.analysis.windows import build_alerts
from app.models import Alert, AnalysisResult, Event, ModelVersion, Run, Segment, Telemetry
from app.services.registry import artifact_file, get_active, load_model

BASELINE_VARS = ("pressure", "flow", "temperature")


def ordered_segments(db: Session) -> list[Segment]:
    return db.query(Segment).order_by(Segment.order_index).all()


def reported_from_db(db: Session, run_id: int, max_tick: int | None = None) -> ReportedRun:
    segments = ordered_segments(db)
    col = {s.id: i for i, s in enumerate(segments)}
    code = {s.id: s.code for s in segments}
    query = db.query(Telemetry.tick, Telemetry.segment_id, Telemetry.pressure_bar, Telemetry.flow_m3h,
                     Telemetry.temperature_c, Telemetry.valve_open_pct, Telemetry.pump_speed_pct
                     ).filter(Telemetry.run_id == run_id)
    if max_tick is not None:
        query = query.filter(Telemetry.tick <= max_tick)
    rows = query.all()
    n_ticks = max(r.tick for r in rows) + 1
    arrays = {k: np.full((n_ticks, len(segments)), np.nan)
              for k in ("pressure", "flow", "temperature", "valve_open", "pump_speed")}
    for r in rows:
        i = col[r.segment_id]
        arrays["pressure"][r.tick, i] = r.pressure_bar
        arrays["flow"][r.tick, i] = r.flow_m3h
        arrays["temperature"][r.tick, i] = r.temperature_c
        if r.valve_open_pct is not None:
            arrays["valve_open"][r.tick, i] = r.valve_open_pct
        if r.pump_speed_pct is not None:
            arrays["pump_speed"][r.tick, i] = r.pump_speed_pct
    ev_query = db.query(Event).filter(Event.run_id == run_id, Event.origin == "simulator", Event.observable.is_(True))
    if max_tick is not None:
        ev_query = ev_query.filter(Event.tick <= max_tick)
    events = [ObservableEvent(e.tick, code.get(e.segment_id), e.source, e.category, e.event_type, e.authorized,
                              e.severity) for e in ev_query.order_by(Event.tick, Event.id).all()]
    return ReportedRun(**arrays, events=events)


def model_for_run(db: Session, run: Run) -> DetectorModel | None:
    if run.model_version_id is None:
        return None
    mv = db.get(ModelVersion, run.model_version_id)
    return load_model(mv) if mv and artifact_file(mv).exists() else None


def _baseline_cell(baseline, t: int, i: int) -> dict:
    cell = {}
    for var in BASELINE_VARS:
        level = int(baseline.level[var][t, i])
        if level:
            cell[var] = "high" if level > 0 else "low"
        elif baseline.rate[var][t, i]:
            cell[var] = "rate"
    return cell


def score_run(db: Session, run: Run) -> bool:
    """Analyse a run with the active model and replace its stored results. False if no model is active."""
    active = get_active(db)
    if active is None:
        return False
    mv, model = active
    reported = reported_from_db(db, run.id)
    out = analyze_run(reported, model)
    seg_ids = [s.id for s in ordered_segments(db)]

    db.execute(delete(AnalysisResult).where(AnalysisResult.run_id == run.id))
    db.execute(delete(Alert).where(Alert.run_id == run.id))
    db.execute(delete(Event).where(Event.run_id == run.id, Event.origin == "analysis"))

    penalised = sum(out.trust.raw_penalties.values()) > 0
    rows = []
    for t in range(reported.n_ticks):
        for i, seg_id in enumerate(seg_ids):
            factors = trust_factors(reported, model.reference, out.checks, out.trust, t, i) if penalised[t, i] else []
            checks = {c: int(out.checks.status[c][t, i]) for c in CHECKS if out.checks.status[c][t, i]}
            rows.append({
                "run_id": run.id, "segment_id": seg_id, "tick": t, "model_version_id": mv.id,
                "anomaly_score": round(float(out.scores[t, i]), 4), "ml_flag": bool(out.ml_flag[t, i]),
                "trust_score": round(float(out.trust.score[t, i]), 4), "trust_status": str(out.trust.status[t, i]),
                "trust_factors": json.dumps(factors), "checks": json.dumps(checks),
                "baseline_alarms": json.dumps(_baseline_cell(out.baseline, t, i)), "state": str(out.state[t, i]),
            })
    db.execute(insert(AnalysisResult), rows)
    if out.alerts:
        db.execute(insert(Alert), [{
            "run_id": run.id, "segment_id": seg_ids[a.seg_idx], "model_version_id": mv.id,
            "start_tick": a.start_tick, "end_tick": a.end_tick, "peak_tick": a.peak_tick, "peak_score": a.peak_score,
            "min_trust": a.min_trust, "kinds": json.dumps(a.kinds), "severity": a.severity, "summary": a.summary,
        } for a in out.alerts])
    if out.events:
        db.execute(insert(Event), [{
            "run_id": run.id, "segment_id": seg_ids[e.seg_idx], "tick": e.tick,
            "timestamp": run.started_at + timedelta(seconds=e.tick * run.tick_seconds), "source": "Sensify Analysis",
            "category": "analysis", "event_type": e.event_type, "authorized": "n/a", "severity": e.severity,
            "details": e.details, "observable": True, "origin": "analysis", "model_version_id": mv.id,
        } for e in out.events])
    run.model_version_id = mv.id
    db.commit()
    return True


def _alert_dict(run: Run, segment: Segment, *, id, start_tick, end_tick, peak_tick, peak_score, min_trust, kinds,
                severity, summary, ongoing) -> dict:
    return {
        "id": id, "run_id": run.id, "run_name": run.name, "segment_id": segment.id, "segment_code": segment.code,
        "segment_name": segment.name, "start_tick": start_tick, "end_tick": end_tick, "peak_tick": peak_tick,
        "peak_score": peak_score, "min_trust": min_trust, "kinds": kinds, "severity": severity, "summary": summary,
        "ongoing": ongoing, "start_time": run.started_at + timedelta(seconds=start_tick * run.tick_seconds),
    }


def results_grid(db: Session, run: Run, cutoff: int) -> dict:
    """Stored per-tick results up to the cutoff, as (T, 6) arrays."""
    segments = ordered_segments(db)
    col = {s.id: i for i, s in enumerate(segments)}
    rows = (db.query(AnalysisResult.tick, AnalysisResult.segment_id, AnalysisResult.anomaly_score,
                     AnalysisResult.ml_flag, AnalysisResult.trust_score, AnalysisResult.trust_status,
                     AnalysisResult.state, AnalysisResult.trust_factors)
            .filter(AnalysisResult.run_id == run.id, AnalysisResult.tick <= cutoff).all())
    n, s = cutoff + 1, len(segments)
    grid = {"scores": np.zeros((n, s)), "ml_flag": np.zeros((n, s), dtype=bool), "trust": np.ones((n, s)),
            "status": np.full((n, s), "Supported", dtype=object), "state": np.full((n, s), "normal", dtype=object),
            "factors": np.full((n, s), "[]", dtype=object)}
    for r in rows:
        i = col[r.segment_id]
        grid["scores"][r.tick, i] = r.anomaly_score or 0.0
        grid["ml_flag"][r.tick, i] = r.ml_flag
        grid["trust"][r.tick, i] = r.trust_score
        grid["status"][r.tick, i] = r.trust_status
        grid["state"][r.tick, i] = r.state
        grid["factors"][r.tick, i] = r.trust_factors
    grid["segments"] = segments
    return grid


def alerts_for_run(db: Session, run: Run, cutoff: int) -> list[dict]:
    if run.model_version_id is None:
        return []
    segments = {s.id: s for s in ordered_segments(db)}
    if cutoff >= run.duration_ticks - 1:
        stored = (db.query(Alert).filter(Alert.run_id == run.id, Alert.model_version_id == run.model_version_id)
                  .order_by(Alert.start_tick, Alert.segment_id).all())
        return [_alert_dict(run, segments[a.segment_id], id=str(a.id), start_tick=a.start_tick, end_tick=a.end_tick,
                            peak_tick=a.peak_tick, peak_score=a.peak_score, min_trust=a.min_trust,
                            kinds=json.loads(a.kinds), severity=a.severity, summary=a.summary, ongoing=False)
                for a in stored]
    grid = results_grid(db, run, cutoff)
    trust = TrustResult(score=grid["trust"], status=grid["status"], raw_penalties={})

    def describe(i: int, t: int) -> str | None:
        factors = json.loads(grid["factors"][t, i])
        return factors[0]["detail"] if factors else None

    records = build_alerts(grid["scores"], grid["ml_flag"], trust, grid["state"], upto=cutoff, describe=describe)
    ordered = grid["segments"]
    return [_alert_dict(run, ordered[a.seg_idx], id=f"{run.id}-{ordered[a.seg_idx].id}-{a.start_tick}",
                        start_tick=a.start_tick, end_tick=a.end_tick, peak_tick=a.peak_tick, peak_score=a.peak_score,
                        min_trust=a.min_trust, kinds=a.kinds, severity=a.severity, summary=a.summary,
                        ongoing=a.end_tick == cutoff)
            for a in records]
