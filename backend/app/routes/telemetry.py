from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Telemetry, User
from app.schemas import TelemetryResponse
from app.auth import get_current_user

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/", response_model=List[TelemetryResponse])
def get_telemetry(
    run_id: int,
    segment_id: Optional[int] = None,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    ground_truth: Optional[bool] = None,
    limit: int = Query(default=500, le=2000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Telemetry).filter(Telemetry.run_id == run_id)

    if segment_id is not None:
        query = query.filter(Telemetry.segment_id == segment_id)

    if from_time:
        try:
            ft = datetime.fromisoformat(from_time)
            query = query.filter(Telemetry.timestamp >= ft)
        except ValueError:
            pass

    if to_time:
        try:
            tt = datetime.fromisoformat(to_time)
            query = query.filter(Telemetry.timestamp <= tt)
        except ValueError:
            pass

    if ground_truth is not None:
        query = query.filter(Telemetry.is_ground_truth == ground_truth)

    telemetry = query.order_by(Telemetry.timestamp.desc()).limit(limit).all()
    return [TelemetryResponse.model_validate(t) for t in telemetry]
