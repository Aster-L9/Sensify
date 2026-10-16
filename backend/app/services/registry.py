"""
Model registry: versions in the database, artifacts in model_store/vN.

Training runs in one background thread so the API stays responsive; the version row
moves from `training` to `ready` or `failed` (with the error), and the active model
is never changed by a training run.
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path, PureWindowsPath

from sqlalchemy.orm import Session

from app.analysis.model import DetectorModel, THRESHOLD
from app.database import SessionLocal
from app.models import ActivityLog, ModelVersion, User

BACKEND_DIR = Path(__file__).resolve().parents[2]
GENERATE_IF_MISSING = True
_cache: dict[int, DetectorModel] = {}
_lock = threading.Lock()


class TrainingInProgress(Exception):
    pass


def model_store_dir() -> Path:
    return Path(os.getenv("MODEL_STORE_DIR") or BACKEND_DIR / "model_store")


def dataset_dir() -> Path:
    return Path(os.getenv("SENSIFY_DATASET_DIR") or BACKEND_DIR / "ml" / "data")


def artifact_file(mv: ModelVersion) -> Path:
    """Where a version's model file lives. Paths are stored relative to the model store so the
    project folder can be moved (or unzipped elsewhere); an old absolute path that no longer
    exists falls back to the store's copy of that version."""
    stored = Path(mv.artifact_path or "")
    if mv.artifact_path:
        if stored.is_absolute():
            if stored.exists():
                return stored
        elif not PureWindowsPath(mv.artifact_path).is_absolute():
            return model_store_dir() / stored
    return model_store_dir() / f"v{mv.version}" / "model.joblib"


def _stored_path(version_dir: Path) -> str:
    file = Path(version_dir) / "model.joblib"
    try:
        return file.resolve().relative_to(model_store_dir().resolve()).as_posix()
    except ValueError:
        return str(file)


def load_model(mv: ModelVersion) -> DetectorModel:
    with _lock:
        if mv.id not in _cache:
            model = DetectorModel.load(artifact_file(mv))
            model.version = mv.version
            _cache[mv.id] = model
        return _cache[mv.id]


def get_active(db: Session) -> tuple[ModelVersion, DetectorModel] | None:
    mv = db.query(ModelVersion).filter(ModelVersion.is_active.is_(True), ModelVersion.status == "ready").first()
    if not mv or not artifact_file(mv).exists():
        return None
    return mv, load_model(mv)


def fail_interrupted_training(db: Session) -> None:
    """A training thread does not survive a restart; mark such versions failed so training can run again."""
    for mv in db.query(ModelVersion).filter(ModelVersion.status == "training").all():
        mv.status, mv.error = "failed", "Training was interrupted by a server restart"
    db.commit()


def _fill_from_dir(mv: ModelVersion, version_dir: Path) -> None:
    manifest = json.loads((version_dir / "manifest.json").read_text(encoding="utf-8"))
    doc = json.loads((version_dir / "metrics.json").read_text(encoding="utf-8"))
    mv.algorithm = manifest["algorithm"]
    mv.feature_spec = manifest["feature_spec"]
    mv.params_json = json.dumps(manifest["params"])
    mv.dataset_json = json.dumps(doc["dataset"])
    mv.metrics_json = json.dumps({"metrics": doc["metrics"], "targets_check": doc["targets_check"],
                                  "headline": manifest["headline"]})
    mv.targets_json = json.dumps(doc["targets"])
    mv.threshold = THRESHOLD
    mv.artifact_path = _stored_path(version_dir)
    mv.trained_seconds = manifest.get("trained_seconds")
    mv.status, mv.error = "ready", None


def activate(db: Session, version_id: int) -> ModelVersion:
    mv = db.get(ModelVersion, version_id)
    if mv is None:
        raise LookupError("Model version not found")
    if mv.status != "ready":
        raise ValueError("Only a ready model can be activated")
    for other in db.query(ModelVersion).filter(ModelVersion.is_active.is_(True)).all():
        other.is_active = False
    mv.is_active = True
    db.commit()
    return mv


def register_from_dir(db: Session, version_dir: Path, user_id: int | None, activate_now: bool) -> ModelVersion:
    manifest = json.loads((Path(version_dir) / "manifest.json").read_text(encoding="utf-8"))
    mv = db.query(ModelVersion).filter(ModelVersion.version == manifest["version"]).first()
    if mv is None:
        mv = ModelVersion(version=manifest["version"], created_by=user_id,
                          created_at=datetime.fromisoformat(manifest["created_at"]).replace(tzinfo=None))
        db.add(mv)
    _fill_from_dir(mv, Path(version_dir))
    db.commit()
    if activate_now:
        activate(db, mv.id)
    return mv


def ensure_seed_model(db: Session) -> None:
    """Register and activate a locally available v1 model on a fresh database."""
    if db.query(ModelVersion).first():
        return
    v1 = model_store_dir() / "v1"
    if (v1 / "manifest.json").exists():
        register_from_dir(db, v1, None, activate_now=True)


def next_version(db: Session) -> int:
    in_db = [v for (v,) in db.query(ModelVersion.version).all()]
    on_disk = [int(p.name[1:]) for p in model_store_dir().glob("v*") if p.name[1:].isdigit()]
    return max(in_db + on_disk, default=0) + 1


def _train_worker(version_id: int, params, user_id: int | None) -> None:
    from ml.train import train_model

    db = SessionLocal()
    try:
        mv = db.get(ModelVersion, version_id)
        try:
            result = train_model(params, dataset_dir(), model_store_dir(), mv.version,
                                 generate_if_missing=GENERATE_IF_MISSING)
            _fill_from_dir(mv, result.version_dir)
            db.add(ActivityLog(user_id=user_id, action="model_trained", entity_type="model", entity_id=mv.id,
                               details=f"Trained model v{mv.version}", timestamp=datetime.utcnow()))
        except Exception as exc:  # the failure is recorded on the version row
            mv.status, mv.error = "failed", f"{type(exc).__name__}: {exc}"[:2000]
        db.commit()
    finally:
        db.close()


def start_training(db: Session, params, user: User) -> ModelVersion:
    if db.query(ModelVersion).filter(ModelVersion.status == "training").first():
        raise TrainingInProgress("A model is already training")
    from dataclasses import asdict

    mv = ModelVersion(version=next_version(db), status="training", algorithm="isolation_forest",
                      params_json=json.dumps(asdict(params)), created_by=user.id, created_at=datetime.utcnow())
    db.add(mv)
    db.commit()
    threading.Thread(target=_train_worker, args=(mv.id, params, user.id), daemon=True).start()
    return mv
