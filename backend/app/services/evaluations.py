"""Evaluation runs: the shipped result, admin re-runs in a background thread, and API shaping."""
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ActivityLog, EvaluationRun, ModelVersion, User
from app.services import registry

EVALUATIONS_DIR = Path(__file__).resolve().parents[2] / "evaluations"
SCENARIO_BREAKDOWNS = {"per_type", "by_type", "splits"}


class EvaluationInProgress(Exception):
    pass


class NoActiveModel(Exception):
    pass


def _utcnow() -> datetime:
    """Naive UTC time, matching the other timestamps stored in SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_seed_evaluation(db: Session) -> None:
    if db.query(EvaluationRun).first():
        return
    f = EVALUATIONS_DIR / "e1" / "results.json"
    if not f.exists():
        return
    doc = json.loads(f.read_text(encoding="utf-8"))
    db.add(EvaluationRun(version=1, status="ready", shipped=True, results=json.dumps(doc),
                         model_version=doc.get("model_version"), engine_version=doc.get("engine_version"),
                         created_at=_utcnow()))
    db.commit()


def fail_interrupted_evaluations(db: Session) -> None:
    for ev in db.query(EvaluationRun).filter(EvaluationRun.status == "running").all():
        ev.status, ev.error = "failed", "Evaluation was interrupted by a server restart"
    db.commit()


def _worker(eval_id: int, model_version_id: int, user_id: int | None) -> None:
    db = SessionLocal()
    try:
        ev = db.get(EvaluationRun, eval_id)
        try:
            from ml import evaluate as ev_mod

            t0 = time.time()
            model = registry.load_model(db.get(ModelVersion, model_version_id))
            result = ev_mod.evaluate(model, ev_mod.default_datasets())
            try:
                ev_mod.write_evaluation(result, EVALUATIONS_DIR, ev.version)
            except Exception:
                pass  # the database row is the record; the files are a convenience
            ev.results = json.dumps(result, default=str)
            ev.engine_version = result.get("engine_version")
            ev.seconds = round(time.time() - t0, 1)
            ev.status, ev.error = "ready", None
        except Exception as exc:
            ev.status, ev.error = "failed", f"{type(exc).__name__}: {exc}"[:2000]
        db.commit()
    finally:
        db.close()


def start_evaluation(db: Session, user: User) -> EvaluationRun:
    if db.query(EvaluationRun).filter(EvaluationRun.status == "running").first():
        raise EvaluationInProgress("An evaluation is already running")
    active = registry.get_active(db)
    if active is None:
        raise NoActiveModel("No active model; activate a model before running an evaluation")
    mv, _ = active
    version = max([v for (v,) in db.query(EvaluationRun.version).all()], default=0) + 1
    ev = EvaluationRun(version=version, status="running", created_by=user.id, model_version=mv.version,
                       created_at=_utcnow())
    db.add(ev)
    db.add(ActivityLog(user_id=user.id, action="evaluation_run", entity_type="evaluation",
                       details=f"Started evaluation e{version}", timestamp=_utcnow()))
    db.commit()
    threading.Thread(target=_worker, args=(ev.id, mv.id, user.id), daemon=True).start()
    return ev


def without_scenario_types(doc):
    """Drops breakdowns keyed by scenario type at any depth: only Admins may see scenario type names."""
    if isinstance(doc, dict):
        return {k: without_scenario_types(v) for k, v in doc.items() if k not in SCENARIO_BREAKDOWNS}
    if isinstance(doc, list):
        return [without_scenario_types(v) for v in doc]
    return doc


def results_for(ev: EvaluationRun, role: str) -> dict | None:
    if not ev.results:
        return None
    res = json.loads(ev.results)
    if role != "admin":
        res.pop("per_run", None)
        res = without_scenario_types(res)
    return res


def evaluation_out(ev: EvaluationRun, detail: bool, role: str = "analyst") -> dict:
    out = {"id": ev.id, "version": ev.version, "status": ev.status, "created_at": ev.created_at,
           "model_version": ev.model_version, "engine_version": ev.engine_version, "error": ev.error,
           "seconds": ev.seconds, "shipped": bool(ev.shipped)}
    if detail:
        out["results"] = results_for(ev, role)
    return out
