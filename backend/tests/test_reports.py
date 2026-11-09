from datetime import datetime
from types import SimpleNamespace

from app.services import investigation as inv


def _fake(monkeypatch):
    run = SimpleNamespace(id=9, name="Run 9", started_at=datetime(2026, 1, 1), tick_seconds=60)
    d = {"key": "9-1", "status": "open", "confidence_label": "Medium", "severity": "high",
         "summary": "Flow fell by 3 m³/h, coincides with ≥ 2 alerts → check.",
         "localisation": {"segment": "S2"}, "actions": ["Check the meter"],
         "evidence": [{"id": "e1", "kind": "alert", "tick": 5, "segment": "S2",
                       "observation": "Flow 12 m³/h", "interpretation": "≥ threshold → consistent with a leak"}]}
    monkeypatch.setattr(inv, "get_incident", lambda db, key: (d, run) if key == "9-1" else None)
    monkeypatch.setattr(inv, "incident_out", lambda d, run, detail: {"classification_label": "Uncertain"})


def test_incident_pdf_and_csv(client, analyst_headers, monkeypatch):
    _fake(monkeypatch)
    r = client.get("/reports/incident/9-1?format=pdf", headers=analyst_headers)
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and len(r.content) > 1000
    assert 'filename="sensify-incident-9-1.pdf"' in r.headers["content-disposition"]
    c = client.get("/reports/incident/9-1?format=csv", headers=analyst_headers)
    assert c.status_code == 200 and "observation" in c.text.splitlines()[0] and "m³" in c.text


def test_incident_pdf_with_chain_and_mitre():
    from app.reports.pdf import incident_pdf

    run = SimpleNamespace(id=9, name="Run 9", started_at=datetime(2026, 1, 1), tick_seconds=60)
    d = {"key": "9-1", "status": "open", "status_note": "checked", "confidence_label": "High",
         "severity": "high", "summary": "s", "actions": ["Check"], "evidence": [],
         "localisation": {"segment": "S2", "ot_layers": ["control", "reporting"], "note": "n"},
         "chain": [{"label": "Unauthorized command", "tick": 3, "segment": "S2"}],
         "mitre": [{"technique_id": "T0855", "name": "Unauthorized Command Message",
                    "tactic": "Impair Process Control", "reason": "r"}]}
    assert incident_pdf(d, run, "Possible cyber manipulation").startswith(b"%PDF")


def test_evaluation_report_pdf(client, analyst_headers, admin_headers):
    r = client.get("/reports/evaluation/1?format=pdf", headers=analyst_headers)
    assert r.status_code == 200 and r.content.startswith(b"%PDF")
    a = client.get("/reports/evaluation/1?format=csv", headers=analyst_headers).text
    b = client.get("/reports/evaluation/1?format=csv", headers=admin_headers).text
    assert a.splitlines()[0] == "dataset,system,criterion,value,target,met"
    assert not any(line.startswith("per_run,") for line in a.splitlines())
    assert any(line.startswith("per_run,") for line in b.splitlines())
    lines = a.splitlines()
    for ds in ("development", "heldout"):
        for crit in ("classification_accuracy", "unexplained_per_normal_run"):
            assert any(line.startswith(f"{ds},C,{crit},") for line in lines), (ds, crit)
        assert f"{ds},A,classification_accuracy,not available,," in lines


def test_evaluation_pdf_handles_missing_values():
    from app.reports.pdf import evaluation_pdf

    sysdoc = {"detection": {"overall": {"rate": 0.9}, "false_alarm": {"tick_rate": 0.0003}},
              "investigation": {"classification_accuracy": None}}
    results = {"model_version": 1, "engine_version": "i1",
               "datasets": {"development": {"systems": {"A": sysdoc, "C": sysdoc}}},
               "targets_check": {"development": {
                   "detection_rate": {"value": None, "target": 0.9, "op": ">=", "passed": False},
                   "x": {"value": {"rate": 0.5}, "target": 0.4, "op": ">=", "passed": True}}}}
    assert evaluation_pdf(SimpleNamespace(version=1), results).startswith(b"%PDF")


def test_unknown_report_is_404(client, analyst_headers):
    assert client.get("/reports/incident/999-9?format=pdf", headers=analyst_headers).status_code == 404
    assert client.get("/reports/evaluation/9999?format=csv", headers=analyst_headers).status_code == 404
