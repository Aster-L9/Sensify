"""Incident endpoints: classified, localised, evidence-linked incidents, never beyond a run's reveal cutoff."""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Run, Segment, User
from app.services import investigation as svc
from app.services.runs import refresh_status, resolve_tick

router = APIRouter(tags=["incidents"])

Classification = Literal["normal_behaviour", "physical_anomaly", "sensor_fault", "cyber_manipulation",
                         "reporting_inconsistency", "uncertain"]


class StatusBody(BaseModel):
    status: Literal["investigating", "resolved"]
    note: Optional[str] = None


def _collect(db: Session, runs: list[Run]) -> list[dict]:
    items = []
    for run in runs:
        refresh_status(db, run)
        items.extend(svc.incident_out(d, run, False) for d in svc.incidents_for_run(db, run, resolve_tick(run, None)))
    return items


@router.get("/incidents")
def list_incidents(
    run_id: Optional[int] = None, classification: Optional[Classification] = None,
    status: Optional[Literal["developing", "investigating", "resolved"]] = None,
    severity: Optional[Literal["low", "medium", "high", "critical"]] = None, segment: Optional[str] = None,
    sort: Literal["detected", "severity", "confidence"] = "detected", order: Literal["desc", "asc"] = "desc",
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    if segment and not db.query(Segment).filter(Segment.code == segment).first():
        raise HTTPException(status_code=404, detail=f"Segment {segment} does not exist")
    query = db.query(Run)
    if run_id is not None:
        query = query.filter(Run.id == run_id)
    runs = query.all()
    if run_id is not None and not runs:
        raise HTTPException(status_code=404, detail="Run not found")
    items = _collect(db, runs)
    for field, value in (("classification", classification), ("status", status), ("severity", severity),
                         ("segment_code", segment)):
        if value:
            items = [i for i in items if i[field] == value]
    sort_key = {"detected": lambda i: (i["detected_time"], i["run_id"]),
                "severity": lambda i: (svc.SEVERITY_RANK.get(i["severity"], 0), i["detected_time"]),
                "confidence": lambda i: (i["confidence"], i["detected_time"])}[sort]
    items.sort(key=sort_key, reverse=order == "desc")
    return items[:limit]


@router.get("/runs/{run_id}/incidents")
def run_incidents(run_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return sorted(_collect(db, [run]), key=lambda i: i["start_tick"])


def _detail(db: Session, key: str) -> dict:
    found = svc.get_incident(db, key)
    if found is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return svc.incident_out(found[0], found[1], True)


@router.get("/incidents/{key}")
def incident_detail(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _detail(db, key)


@router.get("/incidents/{key}/evidence")
def incident_evidence(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _detail(db, key)["evidence"]


@router.get("/incidents/{key}/timeline")
def incident_timeline(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _detail(db, key)["timeline"]


@router.get("/incidents/{key}/trace")
def incident_trace(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"chain": _detail(db, key)["chain"] or []}


@router.get("/incidents/{key}/mitre")
def incident_mitre(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _detail(db, key)["mitre"]


@router.get("/incidents/{key}/recommendations")
def incident_recommendations(key: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _detail(db, key)["actions"]


@router.patch("/incidents/{key}")
def update_incident(key: str, body: StatusBody, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    d, run = svc.set_status(db, key, body.status, body.note, user)
    return svc.incident_out(d, run, True)
