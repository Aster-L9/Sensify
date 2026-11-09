import threading

from app.models import EvaluationRun
from app.services import evaluations


def test_shipped_evaluation_is_visible_to_both(client, admin_headers, analyst_headers):
    r = client.get("/evaluation/latest", headers=analyst_headers)
    assert r.status_code == 200
    res = r.json()["results"]
    assert "development" in res["datasets"] and "heldout" in res["datasets"]
    assert "per_run" not in res
    assert "results" not in client.get("/evaluation", headers=analyst_headers).json()[0]
    assert "per_run" in client.get("/evaluation/latest", headers=admin_headers).json()["results"]


def test_run_evaluation_is_admin_only_and_conflicts(client, admin_headers, analyst_headers, tiny_model,
                                                    no_active_model, monkeypatch, db):
    assert client.post("/evaluation", headers=analyst_headers).status_code == 403
    r = client.post("/evaluation", headers=admin_headers)
    assert r.status_code == 409 and r.json()["detail"]


def test_second_evaluation_while_running_conflicts(client, admin_headers, tiny_model, monkeypatch, db):
    gate = threading.Event()
    monkeypatch.setattr(evaluations, "_worker", lambda *a: gate.wait(10))
    try:
        r = client.post("/evaluation", headers=admin_headers)
        assert r.status_code == 200 and r.json()["status"] == "running"
        assert client.post("/evaluation", headers=admin_headers).status_code == 409
    finally:
        gate.set()
        for ev in db.query(EvaluationRun).filter(EvaluationRun.status == "running"):
            ev.status = "failed"
        db.commit()
