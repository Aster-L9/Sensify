from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Segment, User
from app.schemas import TopologyResponse, SegmentResponse
from app.auth import get_current_user

router = APIRouter(prefix="/topology", tags=["topology"])


@router.get("/", response_model=TopologyResponse)
def get_topology(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    segments = db.query(Segment).order_by(Segment.order_index).all()
    total_length = sum(s.length_km for s in segments)

    return TopologyResponse(
        segments=[SegmentResponse.model_validate(s) for s in segments],
        total_length_km=round(total_length, 2),
        segment_count=len(segments),
    )
