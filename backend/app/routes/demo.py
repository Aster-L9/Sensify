from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import ActivityLog, User
from app.services import registry
from app.services import runs as runs_service
from app.services.demo import DEMO_CONFIG
from app.sim.scenarios import validate_config

router = APIRouter(prefix="/demo", tags=["demo"])


def latest_demo_run_id(db: Session) -> int | None:
    row = (db.query(ActivityLog).filter(ActivityLog.action == "demo_started")
           .order_by(ActivityLog.timestamp.desc(), ActivityLog.id.desc()).first())
    return row.entity_id if row else None


@router.post("")
def start_demo(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if registry.get_active(db) is None:
        raise HTTPException(409, "No active model: activate a model on the Models page before starting the demo")
    run = runs_service.launch_run(db, validate_config(dict(DEMO_CONFIG)), admin, name="Demo run")
    db.add(ActivityLog(user_id=admin.id, action="demo_started", entity_type="run", entity_id=run.id,
                       details="Started the demo run", timestamp=runs_service.utcnow()))
    db.commit()
    return {"run_id": run.id}


@router.get("")
def get_demo(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"run_id": latest_demo_run_id(db)}
