from datetime import datetime, timedelta

from app.services import runs as runs_service
from tests.helpers import launch


def test_alerts_only_revealed_and_filterable(client, admin_headers, analyst_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 10, 1, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    rid = launch(client, admin_headers, magnitude=1.0, onset_min=2).json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(seconds=5))  # 11 ticks revealed, before onset
    assert all(i["end_tick"] <= 10 for i in client.get(f"/alerts?run_id={rid}", headers=analyst_headers).json())
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(minutes=5))
    items = client.get(f"/alerts?run_id={rid}&kind=anomaly", headers=analyst_headers).json()
    assert items and all("anomaly" in i["kinds"] for i in items)
    assert len(client.get("/alerts?limit=1", headers=analyst_headers).json()) == 1
    assert client.get("/alerts?limit=900", headers=analyst_headers).status_code == 422


def test_ongoing_alerts_end_at_the_cutoff(client, admin_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 9, 30, 12)  # earlier than other tests' clocks, so this run never looks "future-started"
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    # A replay is flagged by the consistency checks (low trust) regardless of how strong the model is.
    rid = launch(client, admin_headers, scenario_type="telemetry_manipulation", method="replay",
                 target_segment="SEG-03", magnitude=0.9, onset_min=2).json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(seconds=40))  # 81 ticks: mid-incident
    items = client.get(f"/alerts?run_id={rid}", headers=admin_headers).json()
    assert items and all(i["end_tick"] <= 80 for i in items) and any(i["ongoing"] for i in items)


def test_dashboard_reports_active_run_and_detection(client, admin_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 10, 1, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    launch(client, admin_headers, scenario_type="normal")
    rid = launch(client, admin_headers, magnitude=1.0, onset_min=2).json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(seconds=90))
    s = client.get("/dashboard/summary", headers=admin_headers).json()
    assert s["active_run"]["id"] == rid and s["detection"]["total"] >= 1
    assert sum(s["live"]["segments_by_state"].values()) == 6 and len(s["alerts_per_day"]) == 14
    assert s["live"]["avg_pressure_bar"] > 50 and s["live"]["throughput_m3h"] > 500
