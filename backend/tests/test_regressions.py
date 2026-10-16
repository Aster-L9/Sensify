"""Regression tests for previously fixed bugs."""
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.models import ModelVersion
from app.services import registry
from app.services import runs as runs_service
from tests.helpers import launch


def test_normal_run_accepts_any_duration(client, admin_headers):
    for minutes in (10, 30):
        assert client.post("/scenarios", json={"scenario_type": "normal", "duration_min": minutes, "seed": 1},
                           headers=admin_headers).status_code == 200
    assert client.post("/runs", json={"duration_min": 10}, headers=admin_headers).status_code == 200


def test_stale_training_row_is_failed_on_startup(db):
    db.add(ModelVersion(version=900, status="training", algorithm="isolation_forest"))
    db.commit()
    registry.fail_interrupted_training(db)
    row = db.query(ModelVersion).filter(ModelVersion.version == 900).one()
    assert row.status == "failed" and "restart" in row.error
    db.delete(row)
    db.commit()


def test_live_scenario_does_not_count_towards_detection(client, analyst_headers, admin_headers, tiny_model, monkeypatch):
    t0 = datetime(2026, 9, 20, 12)
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0)
    launch(client, admin_headers, magnitude=1.0, onset_min=2)
    before = client.get("/dashboard/summary", headers=admin_headers).json()["detection"]["total"]
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(seconds=90))  # past onset, still playing
    assert client.get("/dashboard/summary", headers=admin_headers).json()["detection"]["total"] == before
    monkeypatch.setattr(runs_service, "utcnow", lambda: t0 + timedelta(minutes=5))  # completed
    assert client.get("/dashboard/summary", headers=admin_headers).json()["detection"]["total"] == before + 1


def test_artifact_paths_are_relative_to_the_model_store(db, tiny_model):
    mv = db.query(ModelVersion).filter(ModelVersion.version == 1).one()
    assert not Path(mv.artifact_path).is_absolute()
    assert registry.artifact_file(mv) == registry.model_store_dir() / "v1" / "model.joblib"


@pytest.mark.parametrize("artifact_path", [
    r"C:\somewhere\else\model_store\v1\model.joblib",
    r"\\missing-server\share\model_store\v1\model.joblib",
    "/missing-sensify-model-store/v1/model.joblib",
])
def test_legacy_absolute_artifact_path_falls_back_to_the_store(db, tiny_model, artifact_path):
    mv = ModelVersion(version=1, artifact_path=artifact_path)
    assert registry.artifact_file(mv) == registry.model_store_dir() / "v1" / "model.joblib"


def test_analysts_see_no_seed_but_see_run_activity(client, admin_headers, analyst_headers, monkeypatch):
    monkeypatch.setattr(runs_service, "utcnow", lambda: datetime(2026, 9, 21, 12))
    rid = launch(client, admin_headers).json()["id"]
    assert "seed" not in client.get(f"/runs/{rid}", headers=analyst_headers).json()
    assert "seed" in client.get(f"/runs/{rid}", headers=admin_headers).json()
    actions = {a["action"] for a in client.get("/activity?limit=100", headers=analyst_headers).json()}
    assert "scenario_launched" in actions and not actions & {"login", "model_trained"}


def test_model_dataset_path_is_not_a_server_path(client, analyst_headers, tiny_model):
    v1 = next(m for m in client.get("/models", headers=analyst_headers).json() if m["version"] == 1)
    path = client.get(f"/models/{v1['id']}", headers=analyst_headers).json()["dataset"].get("path", "")
    assert not Path(path).is_absolute()


def test_oversized_seed_is_a_400_not_a_crash(client, admin_headers):
    r = client.post("/scenarios/", json={"scenario_type": "normal", "seed": 2**63}, headers=admin_headers)
    assert r.status_code == 400 and "seed" in r.json()["detail"]



def test_detection_rate_is_admin_only_and_analysts_get_runs_with_findings(client, admin_headers, analyst_headers,
                                                                          tiny_model):
    # The detection rate needs ground truth (which runs carried a scenario); analysts investigate blind.
    admin = client.get("/dashboard/summary", headers=admin_headers).json()
    analyst = client.get("/dashboard/summary", headers=analyst_headers).json()
    assert admin["detection"] is not None and analyst["detection"] is None
    for s in (admin, analyst):
        f = s["runs_flagged"]
        assert 0 <= f["flagged"] <= f["completed"] == s["completed_runs"]
    assert analyst["runs_flagged"] == admin["runs_flagged"]
