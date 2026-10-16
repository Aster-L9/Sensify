"""
Threshold-monitoring baseline: classic SCADA-style HI/LO limits and a
rate-of-change alarm per segment and variable, kept as a baseline to compare the ML model against.
"""
from dataclasses import dataclass

import numpy as np

from app.analysis.frame import ReportedRun
from app.analysis.reference import ReferenceProfile

VARS = ("pressure", "flow", "temperature")
RATE_SIGMA = 6.0


@dataclass
class BaselineResult:
    level: dict[str, np.ndarray]  # var -> (T, 6) int8: -1 low, 0 ok, 1 high
    rate: dict[str, np.ndarray]  # var -> (T, 6) bool
    any: np.ndarray  # (T, 6) bool


def baseline_alarms(run: ReportedRun, ref: ReferenceProfile) -> BaselineResult:
    level, rate = {}, {}
    any_alarm = np.zeros((run.n_ticks, ref.limits["pressure"].shape[0]), dtype=bool)
    for var in VARS:
        values = getattr(run, var)
        lo, hi = ref.limits[var][:, 0], ref.limits[var][:, 1]
        level[var] = np.where(values > hi, 1, np.where(values < lo, -1, 0)).astype(np.int8)
        jump = np.zeros_like(values)
        jump[1:] = np.abs(np.diff(values, axis=0))
        rate[var] = jump > RATE_SIGMA * np.sqrt(2) * ref.noise_std[var]
        any_alarm |= (level[var] != 0) | rate[var]
    return BaselineResult(level=level, rate=rate, any=any_alarm)


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    ticks = np.flatnonzero(mask)
    if ticks.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(ticks) > 1)
    starts = np.concatenate([[ticks[0]], ticks[breaks + 1]])
    ends = np.concatenate([ticks[breaks], [ticks[-1]]])
    return list(zip(starts.tolist(), ends.tolist()))


def alarm_windows(res: BaselineResult) -> list[dict]:
    windows = []
    for var in VARS:
        n_seg = res.level[var].shape[1]
        for i in range(n_seg):
            for kind, mask in (("high", res.level[var][:, i] == 1), ("low", res.level[var][:, i] == -1),
                               ("rate", res.rate[var][:, i])):
                for start, end in _runs(mask):
                    windows.append({"seg_idx": i, "variable": var, "kind": kind, "start_tick": start, "end_tick": end})
    return sorted(windows, key=lambda w: (w["start_tick"], w["seg_idx"]))
