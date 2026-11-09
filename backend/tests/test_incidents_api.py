from datetime import datetime, timedelta

import pytest

from app.services import runs as runs_service
from tests.helpers import launch


def _at(monkeypatch, t0, seconds=0):
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(seconds=seconds))


def _strong(client, headers, monkeypatch, t0, **kw):
    _at(monkeypatch, t0)
    return launch(client, headers, magnitude=1.0, onset_min=2, **kw).json()["id"]


def test_completed_run_lists_incidents_for_both_roles(client, admin_headers, analyst_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 9, 11, 12)
    rid = _strong(client, admin_headers, monkeypatch, t0)
    _at(monkeypatch, t0, 3 * 3600)
    for headers in (admin_headers, analyst_headers):
        items = client.get(f"/runs/{rid}/incidents", headers=headers).json()
        assert len(items) >= 1 and not any(i["developing"] for i in items)
    r = client.get(f"/incidents?run_id={rid}", headers=analyst_headers)
    assert r.status_code == 200 and r.json()
    texts = [r.text] + [client.get(f"/incidents/{i['key']}", headers=analyst_headers).text for i in r.json()]
    for text in texts:
        assert "scenario_type" not in text and "target_segment" not in text
    key = r.json()[0]["key"]
    for sub in ("evidence", "timeline", "mitre", "recommendations", "trace"):
        assert client.get(f"/incidents/{key}/{sub}", headers=analyst_headers).status_code == 200


def test_playing_run_incidents_are_developing_and_truncated(client, admin_headers, analyst_headers, tiny_model,
                                                            monkeypatch):
    t0 = datetime(2026, 9, 12, 12)
    rid = _strong(client, admin_headers, monkeypatch, t0)
    _at(monkeypatch, t0, 40)  # 81 ticks revealed
    items = client.get(f"/runs/{rid}/incidents", headers=analyst_headers).json()
    assert items and all(i["developing"] and i["status"] == "developing" and i["start_tick"] <= 80 for i in items)
    for i in items:
        d = client.get(f"/incidents/{i['key']}", headers=analyst_headers).json()
        assert all(e["tick"] <= 80 and e["end_tick"] <= 80 for e in d["evidence"])
        assert all(t["tick"] <= 80 for t in d["timeline"])
    r = client.patch(f"/incidents/{items[0]['key']}", json={"status": "resolved"}, headers=analyst_headers)
    assert r.status_code == 409


def test_resolve_and_reopen(client, admin_headers, analyst_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 9, 13, 12)
    rid = _strong(client, admin_headers, monkeypatch, t0)
    _at(monkeypatch, t0, 3 * 3600)
    key = client.get(f"/runs/{rid}/incidents", headers=analyst_headers).json()[0]["key"]
    r = client.patch(f"/incidents/{key}", json={"status": "resolved", "note": "checked"}, headers=analyst_headers)
    assert r.status_code == 200 and r.json()["status"] == "resolved" and r.json()["resolved_by"]
    assert client.get(f"/incidents/{key}", headers=admin_headers).json()["status_note"] == "checked"
    r = client.patch(f"/incidents/{key}", json={"status": "investigating"}, headers=analyst_headers)
    assert r.json()["status"] == "investigating" and r.json()["resolved_by"] is None
    actions = [a["action"] for a in client.get("/activity/?limit=100", headers=analyst_headers).json()]
    assert "incident_resolved" in actions and "incident_reopened" in actions
    assert client.patch(f"/incidents/{key}", json={"status": "bogus"}, headers=analyst_headers).status_code == 422


def test_unknown_key_is_404(client, analyst_headers, tiny_model):
    assert client.get("/incidents/999-0", headers=analyst_headers).status_code == 404
    assert client.get("/incidents/abc", headers=analyst_headers).status_code == 404
    assert client.patch("/incidents/999-0", json={"status": "resolved"}, headers=analyst_headers).status_code == 404
    assert client.get("/incidents").status_code in (401, 403)


def test_normal_run_without_flags_has_empty_list(client, admin_headers, analyst_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 9, 14, 12)
    _at(monkeypatch, t0)
    for seed in range(1, 8):
        rid = launch(client, admin_headers, scenario_type="normal", method=None, target_segment=None,
                     seed=seed).json()["id"]
        _at(monkeypatch, t0, 3 * 3600)
        if not client.get(f"/alerts?run_id={rid}", headers=analyst_headers).json():
            assert client.get(f"/runs/{rid}/incidents", headers=analyst_headers).json() == []
            assert client.get(f"/incidents?run_id={rid}", headers=analyst_headers).json() == []
            return
        _at(monkeypatch, t0)
    pytest.skip("no normal seed 1-7 produced an empty alert list with the tiny model")


def test_trace_is_empty_for_sensor_fault(client, admin_headers, analyst_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 9, 15, 12)
    _at(monkeypatch, t0)
    rid = launch(client, admin_headers, scenario_type="sensor_fault", method="erratic", target_segment="SEG-02",
                 magnitude=1.0, onset_min=2).json()["id"]
    _at(monkeypatch, t0, 3 * 3600)
    items = [i for i in client.get(f"/runs/{rid}/incidents", headers=analyst_headers).json()
             if i["classification"] not in ("cyber_manipulation", "reporting_inconsistency")]
    if not items:
        pytest.skip("the tiny model yields no sensor-fault-like incident for erratic SEG-02")
    assert client.get(f"/incidents/{items[0]['key']}/trace", headers=analyst_headers).json() == {"chain": []}


def test_stored_equals_recomputed(client, admin_headers, tiny_model, monkeypatch, db):
    from app.analysis.pipeline import analyze_run
    from app.investigation import investigate
    from app.models import Run
    from app.services.scoring import model_for_run, reported_from_db

    t0 = datetime(2026, 9, 16, 12)
    rid = _strong(client, admin_headers, monkeypatch, t0)
    _at(monkeypatch, t0, 3 * 3600)
    stored = client.get(f"/runs/{rid}/incidents", headers=admin_headers).json()
    run = db.get(Run, rid)
    model = model_for_run(db, run)
    reported = reported_from_db(db, rid)
    rows = [i.summary_row() for i in investigate(reported, analyze_run(reported, model), model.reference)]
    got = [{"start_tick": s["start_tick"], "end_tick": s["end_tick"], "detected_tick": s["detected_tick"],
            "classification": s["classification"], "confidence": s["confidence"], "segment_code": s["segment_code"],
            "ot_layers": s["ot_layers"], "evidence_count": s["evidence_count"], "severity": s["severity"]}
           for s in stored]
    assert got == rows and rows
