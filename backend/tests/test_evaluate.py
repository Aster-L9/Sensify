import pytest

from app.analysis.model import DetectorModel
from ml.dataset import load_dataset, split
from ml.evaluate import evaluate, write_evaluation
from ml.generate_dataset import generate_dataset
from ml.incident_metrics import dev_labels
from ml.train import TrainParams, train_model


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ev")
    generate_dataset(tmp / "data", seed=5, n_train_normal=4, n_val_normal=2, n_val_scenario=5, n_test_normal=2, n_test_scenario=5)
    train_model(TrainParams(n_estimators=30), tmp / "data", tmp / "store", version=1)
    model = DetectorModel.load(tmp / "store" / "v1" / "model.joblib")
    runs = split(load_dataset(tmp / "data"), "test")
    labels = dev_labels(runs)
    return evaluate(model, {"development": (runs, labels), "heldout": (runs, labels)})


def test_evaluate_reports_three_systems_per_dataset(result):
    for name in ("development", "heldout"):
        systems = result["datasets"][name]["systems"]
        assert set(systems) == {"A", "B", "C"}
        assert systems["A"]["investigation"]["classification_accuracy"] is None
        assert systems["B"]["investigation"]["classification_accuracy"] is None


def test_datasets_are_not_pooled(result):
    d = result["datasets"]
    assert d["development"]["runs"] != d["development"]["runs"] + d["heldout"]["runs"]
    assert {"development", "heldout"} <= set(d)


def test_unexplained_never_exceeds_total(result):
    for d in result["datasets"].values():
        for s in d["systems"].values():
            inv = s["investigation"]
            assert inv["unexplained_per_normal_run"] <= inv["incidents_per_normal_run"]


def test_write_evaluation_creates_report(result, tmp_path):
    out = write_evaluation(result, tmp_path, 1)
    assert (out / "results.json").exists()
    text = (out / "report.md").read_text(encoding="utf-8")
    assert "Held-out" in text and "Development" in text


def test_heldout_only_target_is_not_checked_on_development():
    import json
    from ml.evaluate import ML_DIR
    targets = json.loads((ML_DIR / "targets_investigation.json").read_text(encoding="utf-8"))
    assert targets["ambiguity_handled"]["datasets"] == ["heldout"]
