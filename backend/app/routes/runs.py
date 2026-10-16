from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Run, User, Telemetry, Segment, ActivityLog, RunStatus
from app.schemas import RunCreate, RunResponse, RunStateResponse
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/", response_model=List[RunResponse])
def list_runs(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Run)
    if status:
        query = query.filter(Run.status == status)
    runs = query.order_by(Run.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for run in runs:
        r = RunResponse.model_validate(run)
        if run.creator:
            r.creator_username = run.creator.username
        result.append(r)
    return result


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    r = RunResponse.model_validate(run)
    if run.creator:
        r.creator_username = run.creator.username
    return r


@router.post("/", response_model=RunResponse)
def create_run(
    data: RunCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    run = Run(
        name=data.name,
        description=data.description,
        config_json=data.config_json,
        created_by=admin.id,
        seed=data.seed,
        status=RunStatus.active.value,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    db.add(ActivityLog(
        user_id=admin.id, action="run_created",
        entity_type="run", entity_id=run.id,
        details=f"Created run: {run.name}",
    ))
    db.commit()

    r = RunResponse.model_validate(run)
    r.creator_username = admin.username
    return r


@router.get("/{run_id}/state", response_model=RunStateResponse)
def get_run_state(
    run_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    segments = db.query(Segment).order_by(Segment.order_index).all()
    telemetry_count = db.query(func.count(Telemetry.id)).filter(
        Telemetry.run_id == run_id
    ).scalar()

    latest = db.query(func.max(Telemetry.timestamp)).filter(
        Telemetry.run_id == run_id
    ).scalar()

    seg_data = []
    for seg in segments:
        last_telemetry = (
            db.query(Telemetry)
            .filter(Telemetry.run_id == run_id, Telemetry.segment_id == seg.id, Telemetry.is_ground_truth == False)
            .order_by(Telemetry.timestamp.desc())
            .first()
        )
        seg_info = {
            "id": seg.id,
            "name": seg.name,
            "state": seg.state,
            "type": seg.segment_type,
        }
        if last_telemetry:
            seg_info["pressure_psi"] = last_telemetry.pressure_psi
            seg_info["flow_rate_bph"] = last_telemetry.flow_rate_bph
            seg_info["temperature_f"] = last_telemetry.temperature_f
        seg_data.append(seg_info)

    return RunStateResponse(
        run_id=run.id,
        status=run.status,
        segments=seg_data,
        telemetry_count=telemetry_count,
        latest_telemetry=latest,
    )
