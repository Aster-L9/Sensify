"""Analysis endpoints for one run. Every series stops at the reveal cutoff."""
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.analysis.consistency import CHECKS, check_messages, run_checks
from app.analysis.model import THRESHOLD
from app.analysis.threshold import alarm_windows, baseline_alarms
from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import ActivityLog, AnalysisResult, User
from app.routes.runs import get_run_or_404
from app.services.registry import get_active
from app.services import runs as runs_service
from app.services.runs import resolve_tick
from app.services.scoring import (
    alerts_for_run, model_for_run, ordered_segments, reported_from_db, score_run,
)

router = APIRouter(prefix="/runs", tags=["analysis"])


def _version(run) -> int | None:
    return run.model_version.version if run.model_version else None


@router.get("/{run_id}/anomalies")
def get_anomalies(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = get_run_or_404(db, run_id)
    cutoff = resolve_tick(run, None)
    segments = ordered_segments(db)
    series = {s.id: {"segment_id": s.id, "code": s.code, "scores": [], "flags": []} for s in segments}
    if run.model_version_id is not None:
        rows = (db.query(AnalysisResult.segment_id, AnalysisResult.anomaly_score, AnalysisResult.ml_flag)
                .filter(AnalysisResult.run_id == run.id, AnalysisResult.tick <= cutoff)
                .order_by(AnalysisResult.tick).all())
        for r in rows:
            series[r.segment_id]["scores"].append(r.anomaly_score)
            series[r.segment_id]["flags"].append(r.ml_flag)
    windows = [a for a in alerts_for_run(db, run, cutoff) if "anomaly" in a["kinds"]]
    return {"run_id": run.id, "model_version": _version(run), "threshold": THRESHOLD, "cutoff_tick": cutoff,
            "segments": list(series.values()), "windows": windows}


@router.get("/{run_id}/telemetry-trust")
def get_trust(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = get_run_or_404(db, run_id)
    cutoff = resolve_tick(run, None)
    segments = ordered_segments(db)
    out = {s.id: {"segment_id": s.id, "code": s.code, "trust": [], "status": [], "factors": [],
                  "current": None, "series_factors_at_min": []} for s in segments}
    if run.model_version_id is not None:
        rows = (db.query(AnalysisResult.segment_id, AnalysisResult.trust_score, AnalysisResult.trust_status,
                         AnalysisResult.trust_factors)
                .filter(AnalysisResult.run_id == run.id, AnalysisResult.tick <= cutoff)
                .order_by(AnalysisResult.tick).all())
        for r in rows:
            seg = out[r.segment_id]
            seg["trust"].append(r.trust_score)
            seg["status"].append(r.trust_status)
            seg["factors"].append(r.trust_factors)
    for seg in out.values():
        factors = seg.pop("factors")
        if seg["trust"]:
            low = min(range(len(seg["trust"])), key=seg["trust"].__getitem__)
            seg["current"] = {"score": seg["trust"][-1], "status": seg["status"][-1], "factors": json.loads(factors[-1])}
            seg["series_factors_at_min"] = json.loads(factors[low])
            seg["min_tick"] = low
    return {"run_id": run.id, "model_version": _version(run), "cutoff_tick": cutoff, "segments": list(out.values())}


@router.get("/{run_id}/consistency")
def get_consistency(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = get_run_or_404(db, run_id)
    cutoff = resolve_tick(run, None)
    segments = ordered_segments(db)
    model = model_for_run(db, run)
    if model is None:
        return {"run_id": run.id, "model_version": None, "cutoff_tick": cutoff,
                "segments": [{"segment_id": s.id, "code": s.code, "series": {}, "latest": {}, "messages": []}
                             for s in segments]}
    reported = reported_from_db(db, run.id, max_tick=cutoff)
    res = run_checks(reported, model.reference)
    return {"run_id": run.id, "model_version": _version(run), "cutoff_tick": cutoff, "segments": [{
        "segment_id": s.id, "code": s.code,
        "series": {c: res.status[c][:, i].tolist() for c in CHECKS},
        "latest": {c: int(res.status[c][cutoff, i]) for c in CHECKS},
        "messages": check_messages(reported, model.reference, res, cutoff, i),
    } for i, s in enumerate(segments)]}


@router.get("/{run_id}/baseline-alarms")
def get_baseline_alarms(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = get_run_or_404(db, run_id)
    cutoff = resolve_tick(run, None)
    segments = ordered_segments(db)
    model = model_for_run(db, run)
    if model is None:
        return {"run_id": run.id, "model_version": None, "cutoff_tick": cutoff, "windows": []}
    res = baseline_alarms(reported_from_db(db, run.id, max_tick=cutoff), model.reference)
    windows = [{**{k: v for k, v in w.items() if k != "seg_idx"}, "segment_id": segments[w["seg_idx"]].id,
                "code": segments[w["seg_idx"]].code} for w in alarm_windows(res)]
    return {"run_id": run.id, "model_version": _version(run), "cutoff_tick": cutoff, "windows": windows}


@router.post("/{run_id}/score")
def rescore_run(run_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    run = get_run_or_404(db, run_id)
    active = get_active(db)
    if active is None:
        raise HTTPException(status_code=409, detail="No active model. Train or activate a model first.")
    score_run(db, run)
    db.add(ActivityLog(user_id=admin.id, action="run_rescored", entity_type="run", entity_id=run.id,
                       details=f"Re-scored {run.name} with model v{active[0].version}", timestamp=runs_service.utcnow()))
    db.commit()
    cutoff = resolve_tick(run, None)
    return {"run_id": run.id, "model_version": active[0].version, "alerts": len(alerts_for_run(db, run, cutoff))}
