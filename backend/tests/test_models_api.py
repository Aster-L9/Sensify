import os

from app.services import registry
from tests.helpers import wait_until


def _active_version(client, headers):
    return next(m for m in client.get("/models", headers=headers).json() if m["is_active"])["version"]


def test_models_list_shows_metrics(client, analyst_headers, tiny_model):
    models = client.get("/models", headers=analyst_headers).json()
    v1 = next(m for m in models if m["version"] == 1)
    assert v1["status"] == "ready" and v1["is_active"] and v1["targets_total"] == 8
    detail = client.get(f"/models/{v1['id']}", headers=analyst_headers).json()
    assert "ml" in detail["metrics"] and "per_type" in detail["metrics"]["ml"] and detail["targets_check"]


def test_failed_training_keeps_active_model(client, admin_headers, tiny_model, monkeypatch):
    monkeypatch.setenv("SENSIFY_DATASET_DIR", os.path.join(os.sep, "nonexistent", "sensify-data"))
    monkeypatch.setattr(registry, "GENERATE_IF_MISSING", False)
    v = client.post("/models/train", json={"n_estimators": 50}, headers=admin_headers).json()
    wait_until(lambda: client.get(f"/models/{v['id']}", headers=admin_headers).json()["status"] != "training")
    body = client.get(f"/models/{v['id']}", headers=admin_headers).json()
    assert body["status"] == "failed" and body["error"]
    assert _active_version(client, admin_headers) == 1


def test_train_validation_and_admin_only(client, admin_headers, analyst_headers, tiny_model):
    assert client.post("/models/train", json={"n_estimators": 10}, headers=admin_headers).status_code == 422
    assert client.post("/models/train", json={}, headers=analyst_headers).status_code == 403


def test_train_then_activate_new_version(client, admin_headers, tiny_model):
    v = client.post("/models/train", json={"n_estimators": 50}, headers=admin_headers).json()
    assert v["status"] == "training"
    wait_until(lambda: client.get(f"/models/{v['id']}", headers=admin_headers).json()["status"] != "training")
    assert client.get(f"/models/{v['id']}", headers=admin_headers).json()["status"] == "ready"
    assert _active_version(client, admin_headers) == 1  # training never changes the active model
    assert client.post(f"/models/{v['id']}/activate", headers=admin_headers).status_code == 200
    assert _active_version(client, admin_headers) == v["version"]
    v1_id = next(m["id"] for m in client.get("/models", headers=admin_headers).json() if m["version"] == 1)
    client.post(f"/models/{v1_id}/activate", headers=admin_headers)
