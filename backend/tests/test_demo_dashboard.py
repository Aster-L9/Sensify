from pathlib import Path

import pytest

from app.services.demo import DEMO_CONFIG
from tests.helpers import rep


def test_demo_story_is_pinned():
    from app.analysis.model import DetectorModel
    from app.analysis.pipeline import analyze_run
    from app.investigation.engine import investigate

    path = Path("model_store/v1/model.joblib")
    if not path.exists():
        pytest.skip("model v1 not present")
    model = DetectorModel.load(path)
    run = rep(**DEMO_CONFIG)
    incs = investigate(run, analyze_run(run, model), model.reference)
    assert incs and incs[0].classification == "cyber_manipulation"
    assert len(incs[0].chain) >= 4


def test_demo_endpoint_admin_only(client, admin_headers, analyst_headers, tiny_model):
    assert client.post("/demo", headers=analyst_headers).status_code == 403
    r = client.post("/demo", headers=admin_headers)
    assert r.status_code == 200
    rid = r.json()["run_id"]
    assert isinstance(rid, int)
    assert client.get("/demo", headers=analyst_headers).json() == {"run_id": rid}


def test_dashboard_has_incident_tiles(client, admin_headers, analyst_headers, tiny_model):
    for h in (admin_headers, analyst_headers):
        body = client.get("/dashboard/summary", headers=h).json()
        for k in ("incidents_by_classification", "open_investigations", "latest_evaluation", "demo_run_id"):
            assert k in body
        assert len(body["incidents_by_classification"]) == 6
        assert "uncertain" in body["incidents_by_classification"]
        assert len(body["open_investigations"]) <= 5


def test_demo_without_active_model_is_409(client, admin_headers, no_active_model):
    r = client.post("/demo", headers=admin_headers)
    assert r.status_code == 409 and "No active model" in r.json()["detail"]
