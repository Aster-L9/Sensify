import json

import pytest

from app.analysis.model import DetectorModel
from app.investigation.config import DEFAULT_CONFIG, ENGINE_VERSION
from ml.tune_engine import MODEL_PATH, SNAPSHOT_PATH, load_validation, snapshot


def test_validation_decisions_snapshot():
    if not MODEL_PATH.exists() or not SNAPSHOT_PATH.exists():
        pytest.skip("model v1 or engine snapshot missing")
    stored = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    runs, labels = load_validation()
    current = snapshot(DetectorModel.load(MODEL_PATH), runs, labels, DEFAULT_CONFIG)
    note = ""
    if ENGINE_VERSION != stored["engine_version"]:
        note = (f" Engine version is {ENGINE_VERSION} but the snapshot is {stored['engine_version']}; "
                "a decision change requires a new engine version (design §6.6).")
    assert current["runs"] == stored["runs"], "Validation decisions changed without a new engine version." + note
