import numpy as np
import pytest

from app.analysis.model import DetectorModel, persist_flags
from app.analysis.threshold import alarm_windows, baseline_alarms
from tests.helpers import normal_runs, rep


@pytest.fixture(scope="module")
def model():
    return DetectorModel.fit(normal_runs(10, start_seed=600), normal_runs(4, start_seed=700), n_estimators=60)


def test_calibration_puts_normal_below_threshold(model):
    s = model.score(rep(scenario_type="normal", seed=401))
    assert np.median(s) < 0.3 and persist_flags(s).mean() < 0.02


def test_normal_ticks_score_well_below_threshold(model):
    s = model.score(rep(scenario_type="normal", seed=402))
    assert np.median(s) < 0.15 and np.quantile(s, 0.9) < 0.5


def test_valve_closure_scores_high(model):
    # Small test model: assert "high" severity (> 0.7); the full 60-run model reaches ~0.92 (critical).
    s = model.score(rep(scenario_type="unauthorized_control", method="valve_close", target_segment="SEG-05", magnitude=1.0, seed=6))
    assert s[100:150].max() > 0.7 and persist_flags(s)[100:150].any()


def test_save_load_roundtrip(model, tmp_path):
    run = rep(scenario_type="normal", seed=402)
    model.save(tmp_path / "m.joblib")
    assert np.allclose(DetectorModel.load(tmp_path / "m.joblib").score(run), model.score(run))


def test_persist_flags_needs_three_of_four():
    s = np.zeros((8, 6))
    s[[2, 3], 0] = 0.9  # two ticks only: never flagged
    s[[2, 3, 5], 1] = 0.9  # third high tick inside a 4-tick window
    f = persist_flags(s)
    assert not f[:, 0].any() and f[5, 1] and not f[4, 1] and not f[3, 1]


def test_calibration_is_cross_fitted_on_unseen_scores():
    train, val = normal_runs(8, start_seed=600), normal_runs(2, start_seed=700)
    m = DetectorModel.fit(train, val, n_estimators=40, calibration_folds=4)
    assert m.params["calibration"] == "cross-fit" and m.params["calibration_samples"] == 10 * 240
    flags = np.mean([persist_flags(m.score(r)).mean() for r in normal_runs(4, start_seed=900)])
    assert flags < 0.02


def test_threshold_limits_miss_replay_but_catch_valve_closure(model):
    valve = baseline_alarms(rep(scenario_type="unauthorized_control", method="valve_close", target_segment="SEG-05", magnitude=1.0, seed=6), model.reference)
    replay = baseline_alarms(rep(scenario_type="telemetry_manipulation", method="replay", target_segment="SEG-03", magnitude=0.5, seed=4), model.reference)
    assert valve.level["pressure"][100:150, 3].max() == 1
    # Replayed values stay inside the HI/LO limits; only the loop seams (every 24 ticks) can trip the rate alarm.
    assert all((replay.level[v][:, 2] == 0).all() for v in ("pressure", "flow", "temperature"))
    seam_ticks = {w["start_tick"] for w in alarm_windows(replay) if w["seg_idx"] == 2}
    assert seam_ticks <= {72 + 24 * k for k in range(5)}
    windows = alarm_windows(valve)
    assert any(w["seg_idx"] == 3 and w["variable"] == "pressure" and w["kind"] == "high" for w in windows)
