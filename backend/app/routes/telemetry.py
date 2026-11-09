from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Run, Segment, Telemetry, User
from app.schemas import TelemetryPoint
from app.routes.references import check_tick_range, segment_or_404
from app.services.runs import resolve_tick

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


@router.get("/", response_model=List[TelemetryPoint])
def get_telemetry(
    run_id: int,
    segment_id: Optional[int] = Query(default=None, ge=1),
    from_tick: Optional[int] = Query(default=None, ge=0),
    to_tick: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=5000, ge=1, le=5000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Reported telemetry only, never beyond the run's revealed ticks.

    A segment that does not exist is a 404 and a malformed one a 422, so an empty list always
    means a real segment with no readings in the range (handover DH-05)."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if segment_id is not None:
        segment_or_404(db, segment_id)
    check_tick_range(from_tick, to_tick)
    cutoff = resolve_tick(run, None)
    upper = cutoff if to_tick is None else min(to_tick, cutoff)

    query = (
        db.query(Telemetry, Segment)
        .join(Segment, Telemetry.segment_id == Segment.id)
        .filter(Telemetry.run_id == run_id, Telemetry.tick <= upper)
    )
    if segment_id is not None:
        query = query.filter(Telemetry.segment_id == segment_id)
    if from_tick is not None:
        query = query.filter(Telemetry.tick >= max(from_tick, 0))
    rows = query.order_by(Telemetry.tick, Segment.order_index).limit(limit).all()
    return [TelemetryPoint(
        run_id=t.run_id, segment_id=t.segment_id, segment_code=seg.code, tick=t.tick, timestamp=t.timestamp,
        pressure_bar=t.pressure_bar, flow_m3h=t.flow_m3h, temperature_c=t.temperature_c,
        valve_open_pct=t.valve_open_pct, pump_speed_pct=t.pump_speed_pct,
        valve_state=t.valve_state, equipment_state=t.equipment_state,
    ) for t, seg in rows]
