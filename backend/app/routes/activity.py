from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ActivityLog, User
from app.schemas import ActivityResponse
from app.auth import get_current_user

router = APIRouter(prefix="/activity", tags=["activity"])


@router.get("/", response_model=List[ActivityResponse])
def get_activity(
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(ActivityLog)

    # Analysts only see run-related activity
    if user.role != "admin":
        query = query.filter(
            ActivityLog.action.in_([
                "scenario_launched", "run_rescored", "run_created", "run_completed", "run_stopped",
            ])
        )

    activities = query.order_by(ActivityLog.timestamp.desc()).limit(limit).all()

    result = []
    for act in activities:
        r = ActivityResponse.model_validate(act)
        if act.user:
            r.username = act.user.username
        result.append(r)
    return result
