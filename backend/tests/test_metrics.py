import numpy as np

from ml.dataset import DatasetRun, RunLabels
from ml.metrics import compare_targets, detection_metrics, trust_metrics

T = 240


def fake_run(run_id, scenario_type, start=None, end=None, target=None, compromised=None):
    is_target = np.zeros(6, bool)
    if target is not None:
        is_target[target] = True
    phase = np.full(T, "baseline", dtype=object)
    if start is not None:
        phase[start:end + 1] = "active"
    rc = np.zeros((T, 6), bool)
    if compromised is not None:
        rc[compromised[0]:compromised[1] + 1, target] = True
    labels = RunLabels(phase=phase, is_target=is_target, process_affected=np.zeros((T, 6), bool),
                       reporting_compromised=rc, event_start_tick=start, event_peak_tick=start, event_end_tick=end)
    code = f"SEG-0{target + 1}" if target is not None else None
    return DatasetRun(run_id, "test", scenario_type, None, code, 0.5, None, labels)


def test_detection_metrics_on_handcrafted_runs():
    runs = [fake_run("A", "normal"), fake_run("B", "physical_anomaly", start=100, end=150, target=3)]
    flags = {"A": np.zeros((T, 6), bool), "B": np.zeros((T, 6), bool)}
    flags["B"][104:120, 3] = True
    flags["A"][10:13, 0] = True
    m = detection_metrics(flags, runs)
    assert m["overall"] == {"detected": 1, "total": 1, "rate": 1.0}
    assert m["time_to_detect_s"]["median"] == 20.0
    assert m["false_alarm"]["windows_per_run"] == 1.0 and m["window_precision"] == 0.5
    assert m["localization_hit_rate"] == 1.0 and m["per_type_min_rate"] == 1.0


def test_missed_event_and_roc_auc_with_scores():
    runs = [fake_run("A", "normal"), fake_run("B", "sensor_fault", start=100, end=150, target=1)]
    flags = {"A": np.zeros((T, 6), bool), "B": np.zeros((T, 6), bool)}
    scores = {"A": np.full((T, 6), 0.1), "B": np.full((T, 6), 0.1)}
    scores["B"][100:151, 1] = 0.8
    m = detection_metrics(flags, runs, scores)
    assert m["overall"]["rate"] == 0.0 and m["per_type"]["sensor_fault"]["detected"] == 0
    assert m["roc_auc"] == 1.0 and m["time_to_detect_s"]["median"] is None


def test_trust_metrics():
    runs = [fake_run("C", "telemetry_manipulation", start=60, end=120, target=2, compromised=(60, 120)),
            fake_run("H", "unauthorized_control", start=60, end=120, target=4)]
    status = {"C": np.full((T, 6), "Supported", dtype=object), "H": np.full((T, 6), "Supported", dtype=object)}
    status["C"][80:90, 2] = "Contradicted"
    status["H"][0:24, 0] = "Review"
    m = trust_metrics(status, runs)
    assert m["compromise_detection_rate"] == 1.0 and abs(m["low_trust_rate_honest"] - 24 / (T * 6)) < 1e-9


def test_compare_targets_marks_misses():
    chk = compare_targets({"overall": {"rate": 0.85}}, {"detection_rate": {"metric": "overall.rate", "op": ">=", "value": 0.9}})
    assert chk["detection_rate"]["passed"] is False and chk["detection_rate"]["value"] == 0.85
