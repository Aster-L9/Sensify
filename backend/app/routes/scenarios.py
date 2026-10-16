from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import Segment, User
from app.schemas import ScenarioLaunch
from app.services.runs import launch_run, run_out
from app.sim.scenarios import CATALOG, PLAYBACK_SPEEDS, ScenarioError, validate_config

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

DEFAULTS = {"magnitude": 0.6, "onset_min": 6, "ramp_min": 1, "active_min": 6, "recovery": True,
            "duration_min": 20, "playback_speed": 10, "variable": "pressure"}


@router.get("/")
def get_catalog(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    segments = db.query(Segment).order_by(Segment.order_index).all()
    return {
        "types": CATALOG,
        "segments": [{"id": s.id, "code": s.code, "name": s.name, "segment_type": s.segment_type,
                      "equipment": s.equipment} for s in segments],
        "playback_speeds": list(PLAYBACK_SPEEDS),
        "defaults": DEFAULTS,
    }


@router.post("/")
def launch_scenario(body: ScenarioLaunch, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    raw = body.model_dump(exclude={"name", "description"}, exclude_none=True)
    try:
        cfg = validate_config(raw)
    except ScenarioError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    run = launch_run(db, cfg, admin, name=body.name, description=body.description)
    return run_out(run, admin)
