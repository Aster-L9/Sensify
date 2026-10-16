"""
Reference profile learned from normal runs.

For each adjacent segment pair: the normal flow difference, and a fitted relation
between the pressure drop and the flow (plus valve opening or pump speed where the
pair contains that equipment). For each segment: sensor noise and normal ranges.
Used by the consistency checks and the threshold baseline.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.analysis.frame import ReportedRun
from app.sim.topology import PUMP_IDX, SEGMENT_CODES, VALVE_IDX

N_SEG = len(SEGMENT_CODES)
N_PAIR = N_SEG - 1
VARS = ("pressure", "flow", "temperature")
VALVE_PAIR = VALVE_IDX - 1  # SEG-04 -> SEG-05
PUMP_PAIR = PUMP_IDX - 1  # SEG-02 -> SEG-03
MIN_STD = 1e-3


def mean3(x: np.ndarray) -> np.ndarray:
    """Causal 3-tick mean along time."""
    return pd.DataFrame(x).rolling(3, min_periods=1).mean().to_numpy()


def pair_flow_diff(run: ReportedRun) -> np.ndarray:
    return run.flow[:, 1:] - run.flow[:, :-1]


def pair_dp(run: ReportedRun) -> np.ndarray:
    return run.pressure[:, :-1] - run.pressure[:, 1:]


def pair_design(run: ReportedRun, pair: int) -> np.ndarray:
    q = run.flow[:, pair + 1]
    cols = [np.ones_like(q), q ** 2]
    if pair == VALVE_PAIR:
        opening = np.clip(run.valve_open[:, VALVE_IDX] / 100, 0.05, None)
        cols.append(q ** 2 / opening ** 2)
    if pair == PUMP_PAIR:
        cols.append((run.pump_speed[:, PUMP_IDX] / 100) ** 2)
    return np.column_stack(cols)


def _noise(values: np.ndarray) -> np.ndarray:
    diffs = np.diff(values, axis=0)
    mad = np.median(np.abs(diffs - np.median(diffs, axis=0)), axis=0)
    return np.maximum(mad / 0.6745 / np.sqrt(2), MIN_STD)


@dataclass
class ReferenceProfile:
    pair_flow_mean: np.ndarray  # (5,)
    pair_flow_std: np.ndarray  # (5,) std of the 3-tick mean
    pair_dp_coef: list[np.ndarray]  # 5 coefficient vectors
    pair_dp_resid_std: np.ndarray  # (5,) std of the 3-tick mean residual
    noise_std: dict[str, np.ndarray]  # var -> (6,)
    limits: dict[str, np.ndarray]  # var -> (6, 2) low/high

    @classmethod
    def fit(cls, runs: list[ReportedRun]) -> "ReferenceProfile":
        flow_d = np.vstack([mean3(pair_flow_diff(r)) for r in runs])
        coefs, resid_std = [], []
        for k in range(N_PAIR):
            X = np.vstack([pair_design(r, k) for r in runs])
            y = np.concatenate([pair_dp(r)[:, k] for r in runs])
            coef, *_ = np.linalg.lstsq(X, y, rcond=None)
            coefs.append(coef)
            resid = np.concatenate([mean3((pair_dp(r)[:, k] - pair_design(r, k) @ coef)[:, None])[:, 0] for r in runs])
            resid_std.append(max(resid.std(), MIN_STD))
        noise, limits = {}, {}
        for var in VARS:
            noise[var] = np.median(np.vstack([_noise(getattr(r, var)) for r in runs]), axis=0)
            values = np.vstack([getattr(r, var) for r in runs])
            mean, std = values.mean(axis=0), values.std(axis=0)
            limits[var] = np.column_stack([mean - 4 * std, mean + 4 * std])
        return cls(
            pair_flow_mean=flow_d.mean(axis=0), pair_flow_std=np.maximum(flow_d.std(axis=0), MIN_STD),
            pair_dp_coef=coefs, pair_dp_resid_std=np.array(resid_std), noise_std=noise, limits=limits,
        )

    def pair_dp_expected(self, run: ReportedRun) -> np.ndarray:
        return np.column_stack([pair_design(run, k) @ self.pair_dp_coef[k] for k in range(N_PAIR)])

    def to_dict(self) -> dict:
        return {
            "pair_flow_mean": self.pair_flow_mean.tolist(), "pair_flow_std": self.pair_flow_std.tolist(),
            "pair_dp_coef": [c.tolist() for c in self.pair_dp_coef],
            "pair_dp_resid_std": self.pair_dp_resid_std.tolist(),
            "noise_std": {k: v.tolist() for k, v in self.noise_std.items()},
            "limits": {k: v.tolist() for k, v in self.limits.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ReferenceProfile":
        return cls(
            pair_flow_mean=np.array(d["pair_flow_mean"]), pair_flow_std=np.array(d["pair_flow_std"]),
            pair_dp_coef=[np.array(c) for c in d["pair_dp_coef"]],
            pair_dp_resid_std=np.array(d["pair_dp_resid_std"]),
            noise_std={k: np.array(v) for k, v in d["noise_std"].items()},
            limits={k: np.array(v) for k, v in d["limits"].items()},
        )
