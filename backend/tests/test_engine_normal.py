import numpy as np

from app.sim.engine import simulate_run
from app.sim.scenarios import validate_config


def _normal(seed):
    return simulate_run(validate_config({"scenario_type": "normal", "seed": seed}))


def test_same_seed_is_identical_and_different_seeds_differ():
    a, b, c = _normal(11), _normal(11), _normal(12)
    assert np.array_equal(a.reported["pressure"], b.reported["pressure"])
    assert not np.array_equal(a.reported["pressure"], c.reported["pressure"])


def test_normal_values_in_calibrated_ranges():
    for seed in range(20):
        r = _normal(seed)
        assert r.reported["pressure"].shape == (240, 6)
        assert 760 <= r.actual["flow"].mean() <= 900
        assert 55 <= r.actual["pressure"].min() and r.actual["pressure"].max() <= 82
        assert 38 <= r.actual["temperature"].min() and r.actual["temperature"].max() <= 47


def test_reported_noise_matches_sigma():
    r = _normal(3)
    resid = r.reported["pressure"] - r.actual["pressure"]
    assert 0.05 < resid.std() < 0.11


def test_normal_run_labels_are_clean():
    r = _normal(5)
    assert not r.process_affected.any() and not r.reporting_compromised.any()
    assert set(r.phase) == {"baseline"} and r.summary.expected_root_cause == "Normal Behavior"
    assert all(e.authorized == "yes" for e in r.events)
