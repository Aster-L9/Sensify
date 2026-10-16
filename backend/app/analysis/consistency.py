"""
Process-consistency checks across related variables and neighbouring segments.

Each check yields a level per tick and segment: 0 ok, 1 warn, 2 fail. Pair checks
(flow balance, pressure gradient) are attributed to both members of the pair; a
segment failing on both sides is the "odd one out".
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.analysis.frame import ReportedRun
from app.analysis.reference import (
    N_PAIR, N_SEG, ReferenceProfile, mean3, pair_dp, pair_flow_diff,
)
from app.sim.topology import SEGMENT_CODES

CHECKS = ("flow_balance", "pressure_gradient", "implausible_change", "range", "replay", "flatline")
WARN_Z, FAIL_Z = 4.0, 8.0
JUMP_Z, STEADY_Z = 6.0, 2.0
REPLAY_WINDOW = 12
FLAT_WINDOW = 24
FLAT_RATIO = 0.25
RANGES = {"pressure": (0.0, 120.0), "flow": (0.0, 2000.0)}
UNITS = {"pressure": "bar", "flow": "m³/h"}


@dataclass
class ChecksResult:
    status: dict[str, np.ndarray]  # check -> (T, 6) int8
    pair_z: dict[str, np.ndarray]  # flow_balance / pressure_gradient -> (T, 5)
    odd_one_out: np.ndarray  # (T, 6) bool: pair checks fail on both sides
    one_sided: np.ndarray  # (T, 6) bool: pair checks fail on one side only
    replay_source: np.ndarray  # (T, 6) int: end tick of the earlier identical window, or -1


def _level(z: np.ndarray) -> np.ndarray:
    a = np.abs(z)
    return np.where(a > FAIL_Z, 2, np.where(a > WARN_Z, 1, 0)).astype(np.int8)


def _to_segments(pair_level: np.ndarray) -> np.ndarray:
    seg = np.zeros((pair_level.shape[0], N_SEG), dtype=np.int8)
    seg[:, :-1] = np.maximum(seg[:, :-1], pair_level)
    seg[:, 1:] = np.maximum(seg[:, 1:], pair_level)
    return seg


def _jumps(values: np.ndarray, noise: np.ndarray) -> np.ndarray:
    out = np.zeros_like(values)
    out[1:] = np.abs(np.diff(values, axis=0)) / (np.sqrt(2) * noise)
    return out


def _implausible(run: ReportedRun, ref: ReferenceProfile) -> np.ndarray:
    jp = _jumps(run.pressure, ref.noise_std["pressure"])
    jq = _jumps(run.flow, ref.noise_std["flow"])
    out = np.zeros((run.n_ticks, N_SEG), dtype=np.int8)
    for i in range(N_SEG):
        neighbours = [j for j in (i - 1, i + 1) if 0 <= j < N_SEG]
        steady_neighbours = np.all([(jp[:, j] < STEADY_Z) & (jq[:, j] < STEADY_Z) for j in neighbours], axis=0)
        p_alone = (jp[:, i] > JUMP_Z) & (jq[:, i] < STEADY_Z)
        q_alone = (jq[:, i] > JUMP_Z) & (jp[:, i] < STEADY_Z)
        out[:, i] = np.where(steady_neighbours & (p_alone | q_alone), 2, 0)
    return out


def _range(run: ReportedRun) -> np.ndarray:
    bad = np.zeros((run.n_ticks, N_SEG), dtype=bool)
    for var, (lo, hi) in RANGES.items():
        values = getattr(run, var)
        bad |= (values < lo) | (values > hi)
    return np.where(bad, 2, 0).astype(np.int8)


def _replay(run: ReportedRun) -> tuple[np.ndarray, np.ndarray]:
    status = np.zeros((run.n_ticks, N_SEG), dtype=np.int8)
    source = np.full((run.n_ticks, N_SEG), -1)
    for i in range(N_SEG):
        seen: dict[tuple, int] = {}
        p, q = run.pressure[:, i], run.flow[:, i]
        for t in range(REPLAY_WINDOW - 1, run.n_ticks):
            key = tuple(np.round(p[t - REPLAY_WINDOW + 1:t + 1], 4)) + tuple(np.round(q[t - REPLAY_WINDOW + 1:t + 1], 3))
            if key in seen:
                status[t, i], source[t, i] = 2, seen[key]
            else:
                seen[key] = t
    return status, source


def _flatline(run: ReportedRun, ref: ReferenceProfile) -> np.ndarray:
    flat = np.zeros((run.n_ticks, N_SEG), dtype=bool)
    for var in ("pressure", "flow"):
        std = pd.DataFrame(getattr(run, var)).rolling(FLAT_WINDOW, min_periods=FLAT_WINDOW).std(ddof=0).to_numpy()
        flat |= np.nan_to_num(std, nan=np.inf) < FLAT_RATIO * ref.noise_std[var]
    return np.where(flat, 2, 0).astype(np.int8)


def run_checks(run: ReportedRun, ref: ReferenceProfile) -> ChecksResult:
    fb_z = (mean3(pair_flow_diff(run)) - ref.pair_flow_mean) / ref.pair_flow_std
    pg_z = mean3(pair_dp(run) - ref.pair_dp_expected(run)) / ref.pair_dp_resid_std
    fb_level, pg_level = _level(fb_z), _level(pg_z)
    pair_bad = np.maximum(fb_level, pg_level) >= 1

    left_bad = np.zeros((run.n_ticks, N_SEG), dtype=bool)
    right_bad = np.zeros((run.n_ticks, N_SEG), dtype=bool)
    left_bad[:, 1:] = pair_bad
    right_bad[:, :-1] = pair_bad

    replay, replay_source = _replay(run)
    status = {
        "flow_balance": _to_segments(fb_level),
        "pressure_gradient": _to_segments(pg_level),
        "implausible_change": _implausible(run, ref),
        "range": _range(run),
        "replay": replay,
        "flatline": _flatline(run, ref),
    }
    return ChecksResult(
        status=status, pair_z={"flow_balance": fb_z, "pressure_gradient": pg_z},
        odd_one_out=left_bad & right_bad, one_sided=left_bad ^ right_bad, replay_source=replay_source,
    )


def _fmt_tick(tick: int) -> str:
    seconds = tick * 5
    return f"T+{seconds // 60:02d}:{seconds % 60:02d}"


def check_messages(run: ReportedRun, ref: ReferenceProfile, res: ChecksResult, tick: int, seg_idx: int) -> list[dict]:
    """Plain-language explanations of the checks that are not ok at this tick and segment."""
    msgs = []
    code = SEGMENT_CODES[seg_idx]
    observed_dp = expected_dp = flow_gap = None
    for check in CHECKS:
        level = int(res.status[check][tick, seg_idx])
        if level == 0:
            continue
        status = "fail" if level == 2 else "warn"
        if check in ("flow_balance", "pressure_gradient"):
            for pair, other in ((seg_idx - 1, seg_idx - 1), (seg_idx, seg_idx + 1)):
                if not 0 <= pair < N_PAIR or abs(res.pair_z[check][tick, pair]) <= WARN_Z:
                    continue
                other_code = SEGMENT_CODES[other]
                if check == "flow_balance":
                    if flow_gap is None:
                        flow_gap = mean3(pair_flow_diff(run)) - ref.pair_flow_mean
                    q, q_other = run.flow[tick, seg_idx], run.flow[tick, other]
                    # The check compares the 15 s mean gap with its normal spread; percentages of the
                    # line flow would round a decisive 5 m³/h gap to "0 %".
                    text = (f"Reported flow {q:.0f} m³/h vs {other_code} {q_other:.0f} m³/h: a gap of "
                            f"{abs(flow_gap[tick, pair]):.0f} m³/h over the last 15 s "
                            f"(normally under {WARN_Z * ref.pair_flow_std[pair]:.0f} m³/h)")
                else:
                    if expected_dp is None:
                        # 15 s means, as the check compares them; a single tick can look fine
                        # right after a spike the check is still counting.
                        observed_dp, expected_dp = mean3(pair_dp(run)), mean3(ref.pair_dp_expected(run))
                    up, down = pair, pair + 1
                    text = (f"Pressure difference {SEGMENT_CODES[up]}→{SEGMENT_CODES[down]} averaged "
                            f"{observed_dp[tick, pair]:.2f} bar over the last 15 s; "
                            f"{expected_dp[tick, pair]:.2f} bar expected at the measured flow")
                msgs.append({"check": check, "status": status, "message": text})
        elif check == "implausible_change":
            for var in ("pressure", "flow"):
                values = getattr(run, var)[:, seg_idx]
                jump = abs(values[tick] - values[tick - 1]) if tick > 0 else 0.0
                if jump > JUMP_Z * np.sqrt(2) * ref.noise_std[var][seg_idx]:
                    msgs.append({"check": check, "status": status, "message":
                                 f"Reported {var} at {code} jumped {jump:.2f} {UNITS[var]} in 5 s while neighbouring readings stayed steady"})
        elif check == "range":
            msgs.append({"check": check, "status": status, "message":
                         f"Reported values at {code} are outside the physical range "
                         f"({run.pressure[tick, seg_idx]:.1f} bar, {run.flow[tick, seg_idx]:.0f} m³/h)"})
        elif check == "replay":
            src = int(res.replay_source[tick, seg_idx])
            msgs.append({"check": check, "status": status, "message":
                         f"The last 60 s of readings at {code} exactly repeat an earlier sequence "
                         f"({_fmt_tick(src - REPLAY_WINDOW + 1)}–{_fmt_tick(src)})"})
        elif check == "flatline":
            msgs.append({"check": check, "status": status, "message":
                         f"Readings at {code} have been unnaturally flat for 2 min (no normal sensor noise)"})
    return msgs
