from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Run, Segment, Telemetry, User, RunStatus
from app.schemas import DashboardSummary, RunResponse
from app.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    total_runs = db.query(func.count(Run.id)).scalar()
    active_runs = db.query(func.count(Run.id)).filter(Run.status == RunStatus.active.value).scalar()
    completed_runs = db.query(func.count(Run.id)).filter(Run.status == RunStatus.completed.value).scalar()

    segments = db.query(Segment).all()
    total_segments = len(segments)

    segments_by_state = {}
    for seg in segments:
        state = seg.state
        segments_by_state[state] = segments_by_state.get(state, 0) + 1

    # Determine system status
    critical_count = segments_by_state.get("critical", 0)
    warning_count = segments_by_state.get("warning", 0)
    if critical_count > 0:
        system_status = "critical"
    elif warning_count > 0:
        system_status = "warning"
    elif active_runs > 0:
        system_status = "operational"
    else:
        system_status = "idle"

    # Latest run
    latest_run = db.query(Run).order_by(Run.created_at.desc()).first()
    latest_run_resp = None
    if latest_run:
        latest_run_resp = RunResponse.model_validate(latest_run)
        if latest_run.creator:
            latest_run_resp.creator_username = latest_run.creator.username

    # Total telemetry points
    telemetry_points = db.query(func.count(Telemetry.id)).scalar()

    return DashboardSummary(
        total_runs=total_runs,
        active_runs=active_runs,
        completed_runs=completed_runs,
        total_segments=total_segments,
        segments_by_state=segments_by_state,
        system_status=system_status,
        latest_run=latest_run_resp,
        telemetry_points=telemetry_points,
    )
