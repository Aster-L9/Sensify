"""
Model registry (spec §6.4): versions in the database, artifacts in model_store/vN.

Training runs in one background thread so the API stays responsive; the version row
moves from `training` to `ready` or `failed` (with the error), and the active model
is never changed by a training run.
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

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


class ArtifactUnavailable(Exception):
    """A version's model file cannot be found, neither where it was recorded nor in the model store."""


def _backend_path(env_name: str, default: Path) -> Path:
    """A folder from the environment; a relative value means relative to backend/, not to wherever
    the server happened to be started, so the same .env works on any machine."""
    value = os.getenv(env_name)
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else BACKEND_DIR / path


def model_store_dir() -> Path:
    return _backend_path("MODEL_STORE_DIR", BACKEND_DIR / "model_store")


def dataset_dir() -> Path:
    return _backend_path("SENSIFY_DATASET_DIR", BACKEND_DIR / "ml" / "data")


def _is_absolute_anywhere(raw: str) -> bool:
    """Absolute on any platform: a Windows drive or UNC path, or a rooted POSIX path. pathlib's native
    check alone reads a drive path as relative on macOS and /Users/... as relative on Windows."""
    win = PureWindowsPath(raw)
    return bool(win.drive or win.root) or PurePosixPath(raw).is_absolute()


def artifact_file(mv: ModelVersion) -> Path:
    """Where a version's model file lives. Paths are stored relative to the model store so the
    project folder can be moved (or unzipped elsewhere). A recorded path that is absolute (on any
    platform) and does not exist here, or a relative one that escapes the store or is missing,
    falls back to the store's copy of the same version, so version identity is kept."""
    fallback = model_store_dir() / f"v{mv.version}" / "model.joblib"
    raw = (mv.artifact_path or "").strip()
    if not raw:
        return fallback
    if _is_absolute_anywhere(raw):
        native = Path(raw)
        return native if native.is_absolute() and native.is_file() else fallback
    parts = PurePosixPath(PureWindowsPath(raw).as_posix()).parts  # tolerate backslash separators
    if ".." in parts:
        return fallback
    candidate = model_store_dir().joinpath(*parts)
    return candidate if candidate.is_file() or not fallback.is_file() else fallback


def artifact_available(mv: ModelVersion) -> bool:
    return artifact_file(mv).is_file()


def store_relative_path(version: int) -> str:
    """How every artifact path is stored: relative to the model store, with forward slashes, so the
    same database row resolves on Windows, macOS and Linux wherever the project folder lives."""
    return f"v{version}/model.joblib"


def _stored_path(version_dir: Path) -> str:
    # Versions are always written to model_store/vN; the folder name carries the version.
    return f"{Path(version_dir).name}/model.joblib"


def normalise_artifact_paths(db: Session) -> list[int]:
    """Rewrite older stored paths (absolute, or with backslashes) to the portable form when the store
    holds that version's file. A path whose file is not in the store is left as it is, so nothing is lost.
    Returns the versions that were rewritten."""
    changed = []
    for mv in db.query(ModelVersion).all():
        portable = store_relative_path(mv.version)
        if mv.artifact_path == portable or not (model_store_dir() / portable).is_file():
            continue
        mv.artifact_path = portable
        changed.append(mv.version)
    if changed:
        db.commit()
    return changed


def load_model(mv: ModelVersion) -> DetectorModel:
    with _lock:
        if mv.id not in _cache:
            file = artifact_file(mv)
            if not file.is_file():
                raise ArtifactUnavailable(f"The model file for v{mv.version} is missing from the model store "
                                          f"(expected v{mv.version}/model.joblib)")
            model = DetectorModel.load(file)
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
                                  "headline": manifest["headline"],
                                  "validation": doc.get("validation") or _validation_sidecar(version_dir)})
    mv.targets_json = json.dumps(doc["targets"])
    mv.threshold = THRESHOLD
    mv.artifact_path = _stored_path(version_dir)
    mv.trained_seconds = manifest.get("trained_seconds")
    mv.status, mv.error = "ready", None


def _validation_sidecar(version_dir: Path) -> dict | None:
    """Validation outcomes computed after training for a version trained before they were recorded."""
    file = Path(version_dir) / "validation.json"
    return json.loads(file.read_text(encoding="utf-8")) if file.is_file() else None


def backfill_validation_metrics(db: Session) -> None:
    """Attach a sidecar validation.json to registered versions that lack validation outcomes."""
    changed = False
    for mv in db.query(ModelVersion).filter(ModelVersion.status == "ready").all():
        stored = json.loads(mv.metrics_json or "{}")
        if stored.get("validation"):
            continue
        sidecar = _validation_sidecar(model_store_dir() / f"v{mv.version}")
        if sidecar:
            stored["validation"] = sidecar
            mv.metrics_json = json.dumps(stored)
            changed = True
    if changed:
        db.commit()


def activate(db: Session, version_id: int) -> ModelVersion:
    mv = db.get(ModelVersion, version_id)
    if mv is None:
        raise LookupError("Model version not found")
    if mv.status != "ready":
        raise ValueError("Only a ready model can be activated")
    if not artifact_available(mv):
        raise ValueError(f"The model file for v{mv.version} is missing from the model store, so it cannot be activated")
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
    """Register and activate the shipped model (model_store/v1) on a fresh database."""
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
