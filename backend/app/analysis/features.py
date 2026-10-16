"""
Per-segment feature vectors for the normal-behaviour model.

Every feature at tick t uses only ticks <= t, so scoring a whole run at once gives
the same answers as scoring it live.
"""
import numpy as np
import pandas as pd

from app.analysis.frame import ReportedRun
from app.sim.topology import PUMP_IDX, SEGMENT_CODES, VALVE_IDX

FEATURE_SPEC_VERSION = "f1"
BASE_FEATURES = ["p", "q", "T", "dp_up", "dp_down", "dq_up", "dq_down",
                 "p_std6", "q_std6", "p_step", "q_step", "p_chg24", "q_chg24"]
N_SEG = len(SEGMENT_CODES)


def feature_names(seg_idx: int) -> list[str]:
    names = list(BASE_FEATURES)
    if seg_idx == VALVE_IDX:
        names.append("valve_open")
    if seg_idx == PUMP_IDX:
        names.append("pump_speed")
    return names


def _std6(x: np.ndarray) -> np.ndarray:
    return pd.Series(x).rolling(6, min_periods=2).std(ddof=0).fillna(0.0).to_numpy()


def _step(x: np.ndarray) -> np.ndarray:
    out = np.zeros_like(x)
    out[1:] = np.abs(np.diff(x))
    return out


def _chg24(x: np.ndarray) -> np.ndarray:
    past_mean = pd.Series(x).shift(1).rolling(24, min_periods=1).mean().to_numpy()
    out = x - past_mean
    out[0] = 0.0
    return out


def build_features(run: ReportedRun) -> list[np.ndarray]:
    """One (T, F_i) matrix per segment, columns in feature_names(i) order."""
    p, q, temp = run.pressure, run.flow, run.temperature
    zeros = np.zeros(run.n_ticks)
    matrices = []
    for i in range(N_SEG):
        cols = [
            p[:, i], q[:, i], temp[:, i],
            p[:, i - 1] - p[:, i] if i > 0 else zeros,
            p[:, i] - p[:, i + 1] if i < N_SEG - 1 else zeros,
            q[:, i] - q[:, i - 1] if i > 0 else zeros,
            q[:, i + 1] - q[:, i] if i < N_SEG - 1 else zeros,
            _std6(p[:, i]), _std6(q[:, i]), _step(p[:, i]), _step(q[:, i]),
            _chg24(p[:, i]), _chg24(q[:, i]),
        ]
        if i == VALVE_IDX:
            cols.append(run.valve_open[:, i])
        if i == PUMP_IDX:
            cols.append(run.pump_speed[:, i])
        matrices.append(np.column_stack(cols).astype(float))
    return matrices
