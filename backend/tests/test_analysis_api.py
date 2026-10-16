from datetime import datetime, timedelta

from app.services import runs as runs_service
from tests.helpers import launch


def test_launch_is_scored_and_anomalies_follow_reveal(client, admin_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 10, 1, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    rid = launch(client, admin_headers, magnitude=1.0).json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(seconds=40))  # 81 ticks
    a = client.get(f"/runs/{rid}/anomalies", headers=admin_headers).json()
    assert a["model_version"] == 1 and a["threshold"] == 0.5 and len(a["segments"][0]["scores"]) == 81
    assert all(w["end_tick"] <= 80 for w in a["windows"])


def test_trust_endpoint_lists_factors(client, admin_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 10, 1, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    rid = launch(client, admin_headers, scenario_type="telemetry_manipulation", method="replay",
                 target_segment="SEG-03", magnitude=0.9).json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(days=1))
    seg = client.get(f"/runs/{rid}/telemetry-trust", headers=admin_headers).json()["segments"][2]
    assert "Contradicted" in seg["status"] and seg["series_factors_at_min"][0]["code"] == "replay"


def test_state_consistency_and_baseline_endpoints(client, analyst_headers, admin_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 10, 1, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    rid = launch(client, admin_headers, magnitude=1.0).json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(days=1))
    state = client.get(f"/runs/{rid}/state?at=130", headers=analyst_headers).json()
    assert state["tick"] == 130 and {s["state"] for s in state["segments"]} <= {"normal", "anomalous", "low_trust"}
    assert any(s["anomaly_score"] is not None and s["anomaly_score"] > 0.5 for s in state["segments"])
    cons = client.get(f"/runs/{rid}/consistency", headers=analyst_headers).json()
    assert set(cons["segments"][0]["latest"]) >= {"flow_balance", "replay", "flatline"}
    base = client.get(f"/runs/{rid}/baseline-alarms", headers=analyst_headers).json()
    assert any(w["code"] == "SEG-04" and w["variable"] == "pressure" and w["kind"] == "high" for w in base["windows"])


def test_state_lists_all_trust_factors_at_the_tick(client, analyst_headers, admin_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 10, 1, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    rid = launch(client, admin_headers, scenario_type="telemetry_manipulation", method="replay",
                 target_segment="SEG-03", magnitude=0.9).json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(days=1))
    seg = client.get(f"/runs/{rid}/state?at=130", headers=analyst_headers).json()["segments"][2]
    assert seg["factors"] and seg["factors"][0] == seg["top_factor"] and seg["factors"][0]["code"] == "replay"


def test_launch_without_model_is_unscored(client, admin_headers, no_active_model):
    r = launch(client, admin_headers).json()
    assert r["scored"] is False
    a = client.get(f"/runs/{r['id']}/anomalies", headers=admin_headers).json()
    assert a["model_version"] is None and a["segments"][0]["scores"] == []
    assert client.post(f"/runs/{r['id']}/score", headers=admin_headers).status_code == 409


def test_rescore_replaces_results(client, admin_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 10, 1, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    rid = launch(client, admin_headers, magnitude=1.0).json()["id"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(days=1))
    before = client.get(f"/runs/{rid}/anomalies", headers=admin_headers).json()
    r = client.post(f"/runs/{rid}/score", headers=admin_headers)
    assert r.status_code == 200 and r.json()["model_version"] == 1
    after = client.get(f"/runs/{rid}/anomalies", headers=admin_headers).json()
    assert after["segments"][3]["scores"] == before["segments"][3]["scores"]


def test_rescore_and_activate_are_admin_only(client, analyst_headers, tiny_model):
    assert client.post("/runs/1/score", headers=analyst_headers).status_code == 403
    assert client.post("/models/1/activate", headers=analyst_headers).status_code == 403
