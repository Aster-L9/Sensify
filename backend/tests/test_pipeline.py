import numpy as np
import pytest

from app.analysis.model import DetectorModel
from app.analysis.pipeline import analyze_run
from app.analysis.windows import build_alerts, flag_windows, segment_state
from tests.helpers import normal_runs, rep


@pytest.fixture(scope="module")
def model():
    return DetectorModel.fit(normal_runs(10, start_seed=600), normal_runs(4, start_seed=700), n_estimators=60)


def test_flag_windows_merges_small_gaps_and_drops_blips():
    m = np.zeros(20, bool)
    m[[2, 6, 7, 8, 10, 11, 16]] = True
    assert flag_windows(m) == [(6, 11)]  # gaps of ≤ 2 false ticks merge first, then windows shorter than 2 ticks drop


def test_state_precedence():
    st = segment_state(np.array([[True, True, False]]), np.array([["Review", "Supported", "Supported"]]))
    assert list(st[0]) == ["low_trust", "anomalous", "normal"]


def test_analyze_run_flags_replay_target(model):
    out = analyze_run(rep(scenario_type="telemetry_manipulation", method="replay", target_segment="SEG-03", magnitude=0.8, seed=4), model)
    a = [x for x in out.alerts if x.seg_idx == 2]
    assert a and "low_trust" in a[0].kinds and a[0].severity in {"high", "critical"}
    assert any(e.event_type == "Telemetry trust degraded" and e.seg_idx == 2 for e in out.events)


def test_alerts_truncated_for_active_runs(model):
    out = analyze_run(rep(scenario_type="unauthorized_control", method="valve_close", target_segment="SEG-05", magnitude=1.0, seed=6), model)
    partial = build_alerts(out.scores, out.ml_flag, out.trust, out.state, upto=95)
    assert all(a.end_tick <= 95 for a in partial)


def test_analyze_run_concealed_at_last_segment(model):
    out = analyze_run(rep(scenario_type="concealed_physical_incident", method="leak", target_segment="SEG-06", magnitude=1.0, seed=10), model)
    assert out.state.shape == (240, 6) and np.isfinite(out.scores).all()


def test_alert_summaries_are_plain_language(model):
    out = analyze_run(rep(scenario_type="unauthorized_control", method="valve_close", target_segment="SEG-05", magnitude=1.0, seed=6), model)
    assert out.alerts and all(a.summary and "Anomaly score" in a.summary for a in out.alerts if "anomaly" in a.kinds)


def test_low_trust_only_summaries_start_with_a_capital(model):
    out = analyze_run(rep(scenario_type="telemetry_manipulation", method="replay", target_segment="SEG-03", magnitude=0.8, seed=4), model)
    trust_only = [a for a in out.alerts if a.kinds == ["low_trust"]]
    assert trust_only and all(a.summary[0].isupper() for a in trust_only)
