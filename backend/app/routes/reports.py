"""Downloadable PDF and CSV reports for incidents and evaluations."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import EvaluationRun, User
from app.reports import csv_export, pdf
from app.services import evaluations as ev_svc
from app.services import investigation as inv

router = APIRouter(prefix="/reports", tags=["reports"])


def _send(body, fmt: str, name: str) -> Response:
    media = "application/pdf" if fmt == "pdf" else "text/csv; charset=utf-8"
    return Response(content=body, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{name}.{fmt}"'})


@router.get("/incident/{key}")
def incident_report(key: str, format: Literal["pdf", "csv"] = "pdf", db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    found = inv.get_incident(db, key)
    if found is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    d, run = found
    label = inv.incident_out(d, run, False)["classification_label"]
    if format == "csv":
        return _send(csv_export.incident_csv(d, run, label), "csv", f"sensify-incident-{key}")
    return _send(pdf.incident_pdf(d, run, label), "pdf", f"sensify-incident-{key}")


@router.get("/evaluation/{eval_id}")
def evaluation_report(eval_id: int, format: Literal["pdf", "csv"] = "pdf", db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    ev = db.get(EvaluationRun, eval_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    results = ev_svc.results_for(ev, user.role)
    if results is None:
        raise HTTPException(status_code=404, detail="Evaluation has no results yet")
    if format == "csv":
        return _send(csv_export.evaluation_csv(results), "csv", f"sensify-evaluation-e{ev.version}")
    return _send(pdf.evaluation_pdf(ev, results), "pdf", f"sensify-evaluation-e{ev.version}")
