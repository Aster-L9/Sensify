import pytest

from app.analysis.consistency import check_messages, run_checks
from app.analysis.reference import ReferenceProfile
from tests.helpers import normal_runs, rep


@pytest.fixture(scope="module")
def ref():
    return ReferenceProfile.fit(normal_runs(8, start_seed=200))


def test_normal_run_mostly_ok(ref):
    res = run_checks(rep(scenario_type="normal", seed=300), ref)
    assert (res.status["flow_balance"] == 2).mean() < 0.005 and (res.status["pressure_gradient"] == 2).mean() < 0.005


def test_replay_signature_fires_on_target_only(ref):
    res = run_checks(rep(scenario_type="telemetry_manipulation", method="replay", target_segment="SEG-03", seed=4), ref)
    on = 72
    assert (res.status["replay"][on + 30:on + 60, 2] == 2).all() and (res.status["replay"][:, [0, 1, 3, 4, 5]] == 0).all()


def test_masked_segment_is_odd_one_out(ref):
    res = run_checks(rep(scenario_type="concealed_physical_incident", method="leak", target_segment="SEG-04", magnitude=0.9, seed=8), ref)
    assert res.odd_one_out[100:150, 3].mean() > 0.5


def test_erratic_sensor_is_implausible(ref):
    res = run_checks(rep(scenario_type="sensor_fault", method="erratic", target_segment="SEG-02", magnitude=0.8, seed=2), ref)
    assert (res.status["implausible_change"][72:156, 1] == 2).sum() >= 5


def test_messages_are_plain_language(ref):
    run = rep(scenario_type="physical_anomaly", method="leak", target_segment="SEG-04", magnitude=0.9, seed=3)
    res = run_checks(run, ref)
    msgs = check_messages(run, ref, res, 130, 3)
    assert any(m["check"] == "flow_balance" and "m³/h" in m["message"] for m in msgs)


def test_stuck_sensor_is_flatlined(ref):
    res = run_checks(rep(scenario_type="sensor_fault", method="stuck", target_segment="SEG-04", variable="flow", magnitude=0.8, seed=5), ref)
    assert (res.status["flatline"][110:150, 3] >= 1).all() or (res.status["flow_balance"][110:150, 3] >= 1).mean() > 0.5


def test_reference_roundtrips_through_dict(ref):
    again = ReferenceProfile.from_dict(ref.to_dict())
    run = rep(scenario_type="normal", seed=301)
    assert (again.pair_dp_expected(run) == ref.pair_dp_expected(run)).all()


def test_flow_message_states_the_averaged_gap_in_flow_units(ref):
    run = rep(scenario_type="normal", seed=302)
    run.flow[100:, 3] += 15.0  # SEG-04's meter suddenly reads 15 m³/h high
    res = run_checks(run, ref)
    msgs = [m["message"] for m in check_messages(run, ref, res, 104, 3) if m["check"] == "flow_balance"]
    assert msgs and all("%" not in m for m in msgs)
    assert any("a gap of 15 m³/h" in m for m in msgs)


def test_pressure_message_states_the_averaged_values_the_check_compares(ref):
    import re

    run = rep(scenario_type="normal", seed=303)
    run.pressure[100, 1] += 6.0  # one 6 bar spike at SEG-02; two ticks later the reading is normal again
    res = run_checks(run, ref)
    msgs = [m["message"] for m in check_messages(run, ref, res, 102, 1) if m["check"] == "pressure_gradient"]
    assert msgs
    for m in msgs:
        observed, expected = map(float, re.findall(r"(\d+\.\d+) bar", m)[:2])
        assert abs(observed - expected) > 1.0, m  # never "2.64 bar; 2.64 bar expected"
        assert "15 s" in m
