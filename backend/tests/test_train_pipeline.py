import json
from pathlib import Path

from ml.generate_dataset import generate_dataset
from ml.train import TrainParams, train_model


def test_train_pipeline_smoke(tmp_path):
    generate_dataset(tmp_path / "data", seed=5, n_train_normal=4, n_val_normal=2, n_val_scenario=5, n_test_normal=2, n_test_scenario=5)
    res = train_model(TrainParams(n_estimators=30), tmp_path / "data", tmp_path / "store", version=1)
    d = tmp_path / "store" / "v1"
    assert {"model.joblib", "metrics.json", "report.md", "manifest.json"} <= {p.name for p in d.iterdir()}
    assert 0 <= res.metrics["ml"]["overall"]["rate"] <= 1 and "baseline" in res.metrics and "trust" in res.metrics
    manifest = json.loads((d / "manifest.json").read_text())
    assert manifest["version"] == 1 and manifest["headline"]["targets_passed"].endswith("/8")


def test_missing_dataset_without_generation_fails_cleanly(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        train_model(TrainParams(n_estimators=10), tmp_path / "nothing", tmp_path / "store", version=1, generate_if_missing=False)


def test_report_keeps_small_rates_visible():
    from ml.train import render_report

    doc = json.loads((Path(__file__).resolve().parents[2] / "docs" / "evaluation" / "sprint-2-v1" / "metrics.json").read_text(encoding="utf-8"))
    text = render_report(doc)
    tick_rate = doc["metrics"]["ml"]["false_alarm"]["tick_rate"]
    assert 0 < tick_rate < 0.001
    assert f"{tick_rate * 100:.3f} %" in text  # e.g. 0.035 %, never rounded to 0.0 %
    assert "| Tick false-alarm rate on normal runs | 0.000 |" not in text
