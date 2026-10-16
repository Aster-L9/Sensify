"""Flagged windows across runs, never beyond each run's reveal cutoff."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Run, User
from app.services.runs import refresh_status, resolve_tick
from app.services.scoring import alerts_for_run

router = APIRouter(prefix="/alerts", tags=["alerts"])


def collect_alerts(db: Session, runs: list[Run]) -> list[dict]:
    items = []
    for run in runs:
        refresh_status(db, run)
        items.extend(alerts_for_run(db, run, resolve_tick(run, None)))
    return items


@router.get("/")
def list_alerts(
    run_id: Optional[int] = None,
    segment_id: Optional[int] = None,
    severity: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
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
    items.sort(key=lambda a: (a["start_time"], a["segment_id"]), reverse=True)
    return items[offset:offset + limit]
