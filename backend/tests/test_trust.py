import pytest

from app.analysis.consistency import run_checks
from app.analysis.frame import ObservableEvent
from app.analysis.reference import ReferenceProfile
from app.analysis.trust import compute_trust, trust_factors
from tests.helpers import normal_runs, rep


@pytest.fixture(scope="module")
def ref():
    return ReferenceProfile.fit(normal_runs(8, start_seed=200))


def test_unauthorized_control_stays_supported(ref):
    run = rep(scenario_type="unauthorized_control", method="valve_close", target_segment="SEG-05", magnitude=1.0, seed=6)
    t = compute_trust(run, run_checks(run, ref))
    assert (t.status[90:150] == "Supported").mean() > 0.95


def test_replay_target_is_contradicted(ref):
    run = rep(scenario_type="telemetry_manipulation", method="replay", target_segment="SEG-03", magnitude=0.8, seed=4)
    t = compute_trust(run, run_checks(run, ref))
    assert (t.status[110:150, 2] == "Contradicted").mean() > 0.8


def test_reporting_event_lowers_trust_for_60_ticks(ref):
    run = rep(scenario_type="normal", seed=12)
    run.events.append(ObservableEvent(50, "SEG-02", "Reporting Source", "security", "Reporting configuration change", "unknown", "medium"))
    t = compute_trust(run, run_checks(run, ref))
    assert t.raw_penalties["reporting_event"][50:110, 1].min() > 0 and t.raw_penalties["reporting_event"][111, 1] == 0


def test_factors_explain_low_trust(ref):
    run = rep(scenario_type="telemetry_manipulation", method="replay", target_segment="SEG-03", magnitude=0.8, seed=4)
    checks = run_checks(run, ref)
    t = compute_trust(run, checks)
    f = trust_factors(run, ref, checks, t, 130, 2)
    assert f[0]["code"] == "replay" and f[0]["weight"] == 0.60 and f[0]["detail"]


def test_flatline_is_a_fail(ref):
    res = run_checks(rep(scenario_type="sensor_fault", method="stuck", target_segment="SEG-04", variable="flow", magnitude=0.8, seed=5), ref)
    assert (res.status["flatline"][110:150, 3] == 2).all()


@pytest.mark.parametrize("cfg", [
    dict(scenario_type="physical_anomaly", method="leak", target_segment="SEG-04", magnitude=1.0, seed=3),
    dict(scenario_type="sensor_fault", method="erratic", target_segment="SEG-02", magnitude=0.8, seed=2),
    dict(scenario_type="telemetry_manipulation", method="bias", target_segment="SEG-01", magnitude=0.6, seed=9),
])
def test_every_failed_check_lowers_trust(ref, cfg):
    """Alert summaries for playing runs are explained from stored trust factors only; that matches the
    stored (completed-run) summaries because a check that is not ok always carries a trust penalty."""
    import numpy as np

    from app.analysis.consistency import CHECKS

    run = rep(**cfg)
    res = run_checks(run, ref)
    trust = compute_trust(run, res)
    not_ok = np.any([res.status[c] > 0 for c in CHECKS], axis=0)
    penalised = sum(trust.raw_penalties.values()) > 0
    assert not_ok.any() and not (not_ok & ~penalised).any()
    t, i = map(int, np.argwhere(not_ok)[0])
    assert trust_factors(run, ref, res, trust, t, i)
