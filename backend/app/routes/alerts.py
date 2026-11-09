"""Flagged windows across runs (spec §8), never beyond each run's reveal cutoff.

Time filter (handover DH-10): `from_tick` and `to_tick` are run time in 5 s ticks from each
run's start (T+00:00 is tick 0), both inclusive. A window matches when it overlaps the range,
so a window that starts before `from_tick` and is still open at it is kept. The range is
applied to the windows revealed so far, before pagination; a reversed range is a 400.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Run, User
from app.routes.references import check_tick_range, segment_or_404
from app.services.runs import refresh_status, resolve_tick
from app.services.investigation import incidents_for_run
from app.services.scoring import alerts_for_run

router = APIRouter(prefix="/alerts", tags=["alerts"])


def collect_alerts(db: Session, runs: list[Run]) -> list[dict]:
    items = []
    for run in runs:
        refresh_status(db, run)
        cutoff = resolve_tick(run, None)
        alerts = alerts_for_run(db, run, cutoff)
        incidents = incidents_for_run(db, run, cutoff) if alerts else []
        for a in alerts:
            a["incident_key"] = next((i["key"] for i in incidents
                                      if i["start_tick"] <= a["start_tick"] and a["end_tick"] <= i["end_tick"]), None)
        items.extend(alerts)
    return items


@router.get("/")
def list_alerts(
    run_id: Optional[int] = None,
    segment_id: Optional[int] = Query(default=None, ge=1),
    severity: Optional[str] = None,
    kind: Optional[str] = None,
    from_tick: Optional[int] = Query(default=None, ge=0),
    to_tick: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if segment_id is not None:
        segment_or_404(db, segment_id)
    check_tick_range(from_tick, to_tick)
    query = db.query(Run)
    if run_id is not None:
        query = query.filter(Run.id == run_id)
    runs = query.all()
    if run_id is not None and not runs:
        raise HTTPException(status_code=404, detail="Run not found")
    items = collect_alerts(db, runs)
    if segment_id is not None:
        items = [a for a in items if a["segment_id"] == segment_id]
    if severity:
        items = [a for a in items if a["severity"] == severity]
    if kind:
        items = [a for a in items if kind in a["kinds"]]
    if from_tick is not None:
        items = [a for a in items if a["end_tick"] >= from_tick]
    if to_tick is not None:
        items = [a for a in items if a["start_tick"] <= to_tick]
    items.sort(key=lambda a: (a["start_time"], a["segment_id"]), reverse=True)
    return items[offset:offset + limit]
