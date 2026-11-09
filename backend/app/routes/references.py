"""Shared checks for references in query parameters (handover DH-05, DH-10)."""
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Segment


def segment_or_404(db: Session, segment_id: int) -> Segment:
    """Every run uses the whole pipeline topology, so an existing segment applies to every run."""
    segment = db.get(Segment, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail=f"Segment {segment_id} does not exist")
    return segment


def check_tick_range(from_tick: Optional[int], to_tick: Optional[int]) -> None:
    if from_tick is not None and to_tick is not None and from_tick > to_tick:
        raise HTTPException(status_code=400, detail="The start of the time range is after its end")
