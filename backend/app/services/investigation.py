"""Incident service: store engine output at scoring, recompute live runs causally, apply status changes."""
import json
from collections import OrderedDict
from datetime import timedelta
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.analysis.pipeline import analyze_run
from app.investigation import investigate
from app.investigation.config import ENGINE_VERSION
from app.investigation.types import CATEGORY_LABELS, OT_LAYER_LABELS
from app.models import ActivityLog, Incident, Run, User
from app.services import runs as runs_service
from app.services.runs import refresh_status, resolve_tick
from app.services.scoring import model_for_run, ordered_segments, reported_from_db

_LIVE_CACHE: "OrderedDict[tuple, list[dict]]" = OrderedDict()
_CACHE_MAX = 64
SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def store_incidents(db: Session, run: Run, reported, out, model) -> int:
    """Replace a run's incident rows with the engine output, keeping analyst status for keys that survive."""
    incidents = investigate(reported, out, model.reference)
    old = {i.key: (i.status, i.status_note, i.resolved_by, i.resolved_at)
           for i in db.query(Incident).filter(Incident.run_id == run.id).all()}
    db.execute(delete(Incident).where(Incident.run_id == run.id))
    for inc in incidents:
        key = f"{run.id}-{inc.start_tick}"
        status, note, by, at = old.get(key, ("investigating", None, None, None))
        db.add(Incident(
            run_id=run.id, key=key, model_version_id=run.model_version_id, engine_version=ENGINE_VERSION,
            start_tick=inc.start_tick, end_tick=inc.end_tick, detected_tick=inc.detected_tick,
            classification=inc.classification, confidence=inc.confidence, segment_code=inc.localisation.segment,
            ot_layers=json.dumps(inc.localisation.ot_layers), localisation_note=inc.localisation.note,
            severity=inc.severity, summary=inc.summary, status=status, status_note=note, resolved_by=by,
            resolved_at=at, payload=json.dumps(inc.to_dict())))
    db.commit()
    return len(incidents)


def ensure_incidents(db: Session) -> int:
    """Investigate every scored run that has no incident rows for the current engine version."""
    done = {r for (r,) in db.query(Incident.run_id).filter(Incident.engine_version == ENGINE_VERSION).distinct()}
    count = 0
    for run in db.query(Run).filter(Run.model_version_id.isnot(None)).all():
        if run.id in done:
            continue
        model = model_for_run(db, run)
        if model is None:
            continue
        reported = reported_from_db(db, run.id)
        count += store_incidents(db, run, reported, analyze_run(reported, model), model)
    return count


def _segment_names(db: Session) -> dict[str, str]:
    return {s.code: s.name for s in ordered_segments(db)}


def _stored_dicts(db: Session, run: Run) -> list[dict]:
    names = _segment_names(db)
    users = {u.id: u.username for u in db.query(User).all()}
    rows = (db.query(Incident).filter(Incident.run_id == run.id, Incident.engine_version == ENGINE_VERSION)
            .order_by(Incident.start_tick).all())
    items = []
    for r in rows:
        d = json.loads(r.payload)
        d.update(key=r.key, status=r.status, developing=False, status_note=r.status_note,
                 resolved_by=users.get(r.resolved_by), resolved_at=r.resolved_at,
                 segment_name=names.get(r.segment_code))
        items.append(d)
    return items


def incidents_for_run(db: Session, run: Run, cutoff: int) -> list[dict]:
    if run.model_version_id is None:
        return []
    if cutoff >= run.duration_ticks - 1:
        return [d for d in _stored_dicts(db, run) if d["start_tick"] <= cutoff]
    ck = (run.id, run.model_version_id, cutoff)
    if ck in _LIVE_CACHE:
        _LIVE_CACHE.move_to_end(ck)
        return [dict(d) for d in _LIVE_CACHE[ck]]
    model = model_for_run(db, run)
    if model is None:
        return []
    reported = reported_from_db(db, run.id, max_tick=cutoff)
    names = _segment_names(db)
    items = []
    for inc in investigate(reported, analyze_run(reported, model), model.reference):
        if inc.start_tick > cutoff:
            continue
        d = inc.to_dict()
        d.update(key=f"{run.id}-{inc.start_tick}", status="developing", developing=True, status_note=None,
                 resolved_by=None, resolved_at=None, segment_name=names.get(inc.localisation.segment))
        items.append(d)
    _LIVE_CACHE[ck] = items
    while len(_LIVE_CACHE) > _CACHE_MAX:
        _LIVE_CACHE.popitem(last=False)
    return [dict(d) for d in items]


def incident_out(d: dict, run: Run, detail: bool) -> dict:
    loc = d["localisation"]
    out = {
        "key": d["key"], "run_id": run.id, "run_name": run.name, "status": d["status"],
        "developing": bool(d["developing"]), "classification": d["classification"],
        "classification_label": CATEGORY_LABELS.get(d["classification"], d["classification"]),
        "confidence": d["confidence"], "confidence_label": d["confidence_label"],
        "segment_code": loc["segment"], "segment_name": d.get("segment_name"), "ot_layers": loc["ot_layers"],
        "ot_layer_labels": [OT_LAYER_LABELS.get(x, x) for x in loc["ot_layers"]],
        "localisation_note": loc["note"], "severity": d["severity"], "start_tick": d["start_tick"],
        "end_tick": d["end_tick"], "detected_tick": d["detected_tick"],
        "detected_time": (run.started_at + timedelta(seconds=d["detected_tick"] * run.tick_seconds)).isoformat(),
        "summary": d["summary"], "evidence_count": len(d["evidence"]), "status_note": d.get("status_note"),
        "resolved_by": d.get("resolved_by"),
        "resolved_at": d["resolved_at"].isoformat() if d.get("resolved_at") else None,
    }
    if detail:
        out.update({k: d[k] for k in ("hypotheses", "evidence", "timeline", "chain", "mitre", "actions",
                                      "uncertainty", "windows")})
    return out


def _run_for_key(db: Session, key: str) -> Run | None:
    try:
        run_id = int(key.split("-", 1)[0])
    except ValueError:
        return None
    return db.get(Run, run_id)


def get_incident(db: Session, key: str) -> tuple[dict, Run] | None:
    run = _run_for_key(db, key)
    if run is None:
        return None
    refresh_status(db, run)
    for d in incidents_for_run(db, run, resolve_tick(run, None)):
        if d["key"] == key:
            return d, run
    return None


def set_status(db: Session, key: str, status: Literal["investigating", "resolved"], note: str | None,
               user: User) -> tuple[dict, Run]:
    found = get_incident(db, key)
    if found is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    d, run = found
    if d["developing"]:
        raise HTTPException(status_code=409,
                            detail="This incident is still developing; its status cannot be changed yet")
    row = db.query(Incident).filter(Incident.key == key).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    now = runs_service.utcnow()
    row.status = status
    row.status_note = note
    row.resolved_by = user.id if status == "resolved" else None
    row.resolved_at = now if status == "resolved" else None
    verb = "Resolved" if status == "resolved" else "Reopened"
    db.add(ActivityLog(user_id=user.id, action="incident_resolved" if status == "resolved" else "incident_reopened",
                       entity_type="run", entity_id=run.id, details=f"{verb} incident {key} in {run.name}",
                       timestamp=now))
    db.commit()
    return get_incident(db, key)
