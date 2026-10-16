"""Model management: list versions and metrics; train and activate (admin)."""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import ActivityLog, ModelVersion, User
from app.services import registry
from app.services import runs as runs_service

router = APIRouter(prefix="/models", tags=["models"])


class TrainRequest(BaseModel):
    n_estimators: int = Field(default=150, ge=50, le=400)
    max_samples: int = Field(default=256, ge=64, le=1024)
    alpha: float = Field(default=0.004, ge=0.001, le=0.05)


def model_out(db: Session, mv: ModelVersion, detail: bool = False) -> dict:
    stored = json.loads(mv.metrics_json or "{}")
    check = stored.get("targets_check", {})
    creator = db.get(User, mv.created_by) if mv.created_by else None
    out = {
        "id": mv.id, "version": mv.version, "algorithm": mv.algorithm, "status": mv.status,
        "is_active": mv.is_active, "created_at": mv.created_at,
        "created_by": creator.username if creator else None, "trained_seconds": mv.trained_seconds,
        "error": mv.error, "threshold": mv.threshold, "feature_spec": mv.feature_spec,
        "params": json.loads(mv.params_json or "{}"), "headline": stored.get("headline", {}),
        "targets_passed": sum(1 for c in check.values() if c["passed"]), "targets_total": len(check),
    }
    if detail:
        out.update({"metrics": stored.get("metrics", {}), "targets_check": check,
                    "targets": json.loads(mv.targets_json or "{}"), "dataset": json.loads(mv.dataset_json or "{}")})
    return out


@router.get("/")
def list_models(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [model_out(db, mv) for mv in db.query(ModelVersion).order_by(ModelVersion.version.desc()).all()]


@router.get("/{model_id}")
def get_model(model_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mv = db.get(ModelVersion, model_id)
    if mv is None:
        raise HTTPException(status_code=404, detail="Model version not found")
    return model_out(db, mv, detail=True)


@router.post("/train")
def train(body: TrainRequest, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    from ml.train import TrainParams

    try:
        mv = registry.start_training(db, TrainParams(body.n_estimators, body.max_samples, body.alpha), admin)
    except registry.TrainingInProgress as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return model_out(db, mv)


@router.post("/{model_id}/activate")
def activate_model(model_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    try:
        mv = registry.activate(db, model_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    db.add(ActivityLog(user_id=admin.id, action="model_activated", entity_type="model", entity_id=mv.id,
                       details=f"Activated model v{mv.version}", timestamp=runs_service.utcnow()))
    db.commit()
    return model_out(db, mv)
