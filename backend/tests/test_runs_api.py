from datetime import datetime, timedelta

from app.services import runs as runs_service
from tests.helpers import launch


def test_analyst_cannot_launch_and_bad_config_is_400(client, admin_headers, analyst_headers):
    assert launch(client, analyst_headers).status_code == 403
    assert launch(client, admin_headers, target_segment="SEG-02").status_code == 400


def test_reveal_cutoff_hides_future(client, admin_headers, monkeypatch):
    t0 = datetime(2026, 10, 1, 12, 0, 0)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    run_id = launch(client, admin_headers).json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(seconds=30))  # 30 s × 10 / 5 = 60 → 61 ticks
    rows = client.get(f"/telemetry?run_id={run_id}&segment_id=1&limit=5000", headers=admin_headers).json()
    assert len(rows) == 61 and rows[-1]["tick"] == 60
    assert client.get(f"/runs/{run_id}", headers=admin_headers).json()["status"] == "active"
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(minutes=5))
    assert client.get(f"/runs/{run_id}", headers=admin_headers).json()["status"] == "completed"


def test_time_params_clamped_to_reveal(client, admin_headers, monkeypatch):
    t0 = datetime(2026, 10, 1, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    run_id = launch(client, admin_headers).json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(seconds=10))  # 21 ticks
    assert client.get(f"/runs/{run_id}/state?at=999", headers=admin_headers).json()["tick"] == 20
    assert client.get(f"/runs/{run_id}/state?at=-5", headers=admin_headers).json()["tick"] == 0
    rows = client.get(f"/telemetry?run_id={run_id}&to_tick=239", headers=admin_headers).json()
    assert max(r["tick"] for r in rows) == 20
    assert all(e["tick"] <= 20 for e in client.get(f"/runs/{run_id}/events", headers=admin_headers).json())


def test_analyst_never_sees_ground_truth(client, admin_headers, analyst_headers, monkeypatch):
    t0 = datetime(2026, 10, 1, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    run_id = launch(client, admin_headers, scenario_type="physical_anomaly", method="leak", target_segment="SEG-04").json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(days=1))  # fully revealed
    r = client.get(f"/runs/{run_id}", headers=analyst_headers).json()
    assert not {"scenario_type", "method", "target_segment", "scenario_params"} & r.keys()
    assert client.get(f"/runs/{run_id}/ground-truth", headers=analyst_headers).status_code == 403
    ev = client.get(f"/runs/{run_id}/events?include_ground_truth=true", headers=analyst_headers).json()
    assert all(e["source"] != "Physical Process" for e in ev)
    rows = client.get(f"/telemetry?run_id={run_id}", headers=analyst_headers).json()
    assert rows and not any(k.startswith("actual") for row in rows for k in row)
    admin_ev = client.get(f"/runs/{run_id}/events?include_ground_truth=true", headers=admin_headers).json()
    assert any(e["event_type"] == "Leak begins" for e in admin_ev)


def test_admin_sees_scenario_fields_and_ground_truth(client, admin_headers, monkeypatch):
    t0 = datetime(2026, 10, 1, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    run_id = launch(client, admin_headers, scenario_type="physical_anomaly", method="leak", target_segment="SEG-04").json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(days=1))
    r = client.get(f"/runs/{run_id}", headers=admin_headers).json()
    assert r["scenario_type"] == "physical_anomaly" and r["target_segment"] == "SEG-04" and r["progress"] == 1.0
    gt = client.get(f"/runs/{run_id}/ground-truth", headers=admin_headers).json()
    assert gt["summary"]["event_start_tick"] == 72 and gt["summary"]["target_segment"] == "SEG-04"


def test_catalog_and_topology_shapes(client, analyst_headers):
    cat = client.get("/scenarios", headers=analyst_headers).json()
    assert [t["id"] for t in cat["types"]][0] == "normal" and cat["playback_speeds"] == [1, 5, 10, 20]
    topo = client.get("/topology", headers=analyst_headers).json()
    assert topo["segments"][2]["code"] == "SEG-03" and topo["segments"][2]["equipment"] == "pump"
