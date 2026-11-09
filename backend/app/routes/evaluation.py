"""Evaluation endpoints: shipped and re-run results; running one is admin only."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import EvaluationRun, User
from app.services import evaluations as svc

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.post("")
def run_evaluation(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    try:
        ev = svc.start_evaluation(db, admin)
    except (svc.EvaluationInProgress, svc.NoActiveModel) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return svc.evaluation_out(ev, False, admin.role)


@router.get("")
def list_evaluations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [svc.evaluation_out(e, False, user.role)
            for e in db.query(EvaluationRun).order_by(EvaluationRun.version.desc()).all()]


@router.get("/latest")
def latest(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ev = (db.query(EvaluationRun).filter(EvaluationRun.status == "ready")
          .order_by(EvaluationRun.version.desc()).first())
    if ev is None:
        raise HTTPException(status_code=404, detail="No evaluation available")
    return svc.evaluation_out(ev, True, user.role)


@router.get("/{eval_id}")
def get_evaluation(eval_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ev = db.get(EvaluationRun, eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return svc.evaluation_out(ev, True, user.role)
