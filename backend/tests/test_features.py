import numpy as np

from app.analysis.features import build_features, feature_names
from tests.helpers import rep


def test_features_are_causal():
    run = rep(scenario_type="normal", seed=9)
    f1 = build_features(run)
    run.pressure[150:, :] += 25.0
    run.flow[150:, :] -= 200
    f2 = build_features(run)
    for a, b in zip(f1, f2):
        assert np.array_equal(a[:150], b[:150])


def test_features_edge_segments_have_zero_neighbour_terms():
    run = rep(scenario_type="normal", seed=9)
    feats = build_features(run)
    up = feature_names(0).index("dp_up")
    down = feature_names(5).index("dq_down")
    assert np.all(feats[0][:, up] == 0) and np.all(feats[5][:, down] == 0)
    assert all(np.isfinite(f).all() for f in feats)
    assert feats[4].shape[1] == 14 and feats[2].shape[1] == 14 and feats[0].shape[1] == 13


def test_neighbour_features_expose_a_masked_segment():
    run = rep(scenario_type="concealed_physical_incident", method="leak", target_segment="SEG-04", magnitude=0.9, seed=8)
    feats = build_features(run)
    dq_down = feature_names(3).index("dq_down")
    baseline = feats[3][40:70, dq_down].mean()
    assert feats[3][110:150, dq_down].mean() < baseline - 50
