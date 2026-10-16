import numpy as np

from app.sim.engine import simulate_run
from app.sim.scenarios import validate_config


def run(**kw):
    kw.setdefault("seed", 21)
    kw.setdefault("magnitude", 0.8)
    return simulate_run(validate_config(kw))


def test_unauthorized_valve_close_physics_and_events():
    r = run(scenario_type="unauthorized_control", method="valve_close", target_segment="SEG-05")
    t0, mid = 60, 120
    assert r.actual["flow"][mid, 0] < r.actual["flow"][t0, 0] - 40
    assert r.actual["pressure"][mid, 3] > r.actual["pressure"][t0, 3] + 1.0
    cmds = [e for e in r.events if e.event_type.startswith("Valve command") and e.authorized == "no"]
    assert cmds and all(e.observable for e in cmds)
    assert not r.reporting_compromised.any() and r.process_affected[mid].any()


def test_leak_reduces_downstream_flow_and_is_hidden_event():
    r = run(scenario_type="physical_anomaly", method="leak", target_segment="SEG-04")
    assert r.actual["flow"][120, 3] < r.actual["flow"][120, 2] - 50
    assert any(e.event_type == "Leak begins" and not e.observable for e in r.events)


def test_replay_reports_exact_copies_of_pre_onset_window():
    r = run(scenario_type="telemetry_manipulation", method="replay", target_segment="SEG-03")
    i = 2
    on = r.config.onset_tick
    assert np.array_equal(r.reported["pressure"][on:on + 24, i], r.reported["pressure"][on - 24:on, i])
    assert r.reporting_compromised[on + 30, i] and r.actual["flow"][on + 30, i] < r.actual["flow"][on - 1, i] - 20


def test_concealment_is_normal_looking_but_not_a_copy():
    r = run(scenario_type="concealed_physical_incident", method="leak", target_segment="SEG-04")
    i = 3
    on = r.config.onset_tick
    seg = r.reported["flow"][on + 20:on + 44, i]
    assert abs(seg.mean() - r.reported["flow"][on - 24:on, i].mean()) < 4
    assert not np.array_equal(seg, r.reported["flow"][on - 24:on, i])
    assert r.actual["flow"][on + 30, i] < r.actual["flow"][on - 1, i] - 40


def test_sensor_fault_erratic_leaves_process_unchanged():
    r = run(scenario_type="sensor_fault", method="erratic", target_segment="SEG-02")
    assert not r.process_affected.any() and r.reporting_compromised[:, 1].any()


def test_phases_and_summary():
    r = run(scenario_type="physical_anomaly", method="leak", target_segment="SEG-04")
    s = r.summary
    assert s.event_start_tick == 72 and s.event_end_tick == 180 and 84 <= s.event_peak_tick <= 155
    assert r.phase[0] == "baseline" and r.phase[80] == "onset" and "peak" in set(r.phase) and r.phase[200] == "recovered"
    assert s.expected_root_cause == "Physical/Process Anomaly"


def _catalog_combos():
    from app.sim.scenarios import CATALOG
    for t in CATALOG:
        for m in t["methods"]:
            for target in m["allowed_targets"]:
                yield t["id"], m["id"], target


def test_every_catalog_combination_leaves_a_ground_truth_footprint():
    for scenario_type, method, target in _catalog_combos():
        r = run(scenario_type=scenario_type, method=method, target_segment=target, magnitude=0.7, seed=3)
        i = r.segment_codes.index(target)
        footprint = r.process_affected[:, i].sum() + r.reporting_compromised[:, i].sum()
        assert r.is_target[i] and footprint > 10, (scenario_type, method, target, footprint)
        assert r.summary.event_start_tick == r.config.onset_tick and r.summary.event_peak_tick is not None


def test_scenario_runs_are_deterministic():
    a = run(scenario_type="sensor_fault", method="erratic", target_segment="SEG-02")
    b = run(scenario_type="sensor_fault", method="erratic", target_segment="SEG-02")
    assert np.array_equal(a.reported["pressure"], b.reported["pressure"]) and [e.tick for e in a.events] == [e.tick for e in b.events]
