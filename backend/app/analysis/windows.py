"""
Segment state, flagged windows (alerts) and analysis events.
"""
from dataclasses import dataclass
from typing import Callable

import numpy as np

from app.analysis.consistency import CHECKS, ChecksResult
from app.analysis.trust import REVIEW_MIN, SUPPORTED_MIN, TrustResult
from app.sim.topology import SEGMENT_CODES

CHECK_LABELS = {
    "flow_balance": "Flow balance with a neighbouring segment",
    "pressure_gradient": "Pressure gradient against a neighbouring segment",
    "implausible_change": "Physically implausible change",
    "range": "Value outside the physical range",
    "replay": "Replayed readings",
    "flatline": "Unnaturally flat readings",
}
STATUS_RANK = {"Supported": 0, "Review": 1, "Contradicted": 2}


@dataclass
class AlertRecord:
    seg_idx: int
    start_tick: int
    end_tick: int
    peak_tick: int
    peak_score: float | None
    min_trust: float
    kinds: list[str]
    severity: str
    summary: str


@dataclass
class AnalysisEvent:
    tick: int
    seg_idx: int
    event_type: str
    severity: str
    details: str


def segment_state(ml_flag: np.ndarray, trust_status: np.ndarray) -> np.ndarray:
    """Map state per tick and segment: low_trust takes precedence over anomalous."""
    return np.where(trust_status != "Supported", "low_trust", np.where(ml_flag, "anomalous", "normal")).astype(object)


def flag_windows(mask: np.ndarray, max_gap: int = 2, min_len: int = 2) -> list[tuple[int, int]]:
    """Contiguous runs of True (inclusive bounds); gaps of <= max_gap False ticks merge, then short runs drop."""
    ticks = np.flatnonzero(mask)
    if ticks.size == 0:
        return []
    windows = [[int(ticks[0]), int(ticks[0])]]
    for t in ticks[1:]:
        if t - windows[-1][1] - 1 <= max_gap:
            windows[-1][1] = int(t)
        else:
            windows.append([int(t), int(t)])
    return [(s, e) for s, e in windows if e - s + 1 >= min_len]


def _severity(peak_score: float | None, min_trust: float) -> str:
    peak = peak_score or 0.0
    if peak >= 0.9 or min_trust < REVIEW_MIN:
        return "critical"
    if peak >= 0.7 or min_trust < 0.55:
        return "high"
    return "medium"


def build_alerts(scores: np.ndarray, ml_flag: np.ndarray, trust: TrustResult, state: np.ndarray,
                 upto: int | None = None, describe: Callable[[int, int], str | None] | None = None) -> list[AlertRecord]:
    """Flagged windows per segment. `upto` (inclusive) truncates for runs still playing."""
    end = state.shape[0] if upto is None else upto + 1
    alerts = []
    for i in range(state.shape[1]):
        for s, e in flag_windows(state[:end, i] != "normal"):
            window_scores = scores[s:e + 1, i]
            peak_tick = s + int(np.argmax(window_scores))
            peak_score = float(window_scores.max())
            trust_window = trust.score[s:e + 1, i]
            min_trust = float(trust_window.min())
            kinds = []
            if ml_flag[s:e + 1, i].any():
                kinds.append("anomaly")
            if (trust.status[s:e + 1, i] != "Supported").any():
                kinds.append("low_trust")
            parts = []
            if "anomaly" in kinds:
                parts.append(f"Anomaly score peaked at {peak_score:.2f}")
            if "low_trust" in kinds:
                low_tick = s + int(np.argmin(trust_window))
                parts.append(f"telemetry trust fell to {min_trust:.2f} ({trust.status[low_tick, i]})")
            summary = "; ".join(parts)
            summary = summary[:1].upper() + summary[1:]
            if describe:
                detail = describe(i, s + int(np.argmin(trust_window)) if "low_trust" in kinds else peak_tick)
                if detail:
                    summary = f"{summary}. {detail}" if summary else detail
            alerts.append(AlertRecord(i, s, e, peak_tick, peak_score, min_trust, kinds,
                                      _severity(peak_score if "anomaly" in kinds else None, min_trust), summary))
    return sorted(alerts, key=lambda a: (a.start_tick, a.seg_idx))


def analysis_events(scores: np.ndarray, ml_flag: np.ndarray, checks: ChecksResult, trust: TrustResult) -> list[AnalysisEvent]:
    events = []
    for i, code in enumerate(SEGMENT_CODES):
        for s, e in flag_windows(ml_flag[:, i]):
            window = scores[s:e + 1, i]
            peak_tick, peak = s + int(np.argmax(window)), float(window.max())
            events.append(AnalysisEvent(s, i, "High anomaly score", "critical" if scores[s, i] >= 0.9 else "high",
                                        f"Anomaly score {scores[s, i]:.2f} at {code} (threshold 0.50)"))
            if peak >= 0.9 and peak_tick != s:
                events.append(AnalysisEvent(peak_tick, i, "High anomaly score", "critical",
                                            f"Anomaly score peaked at {peak:.2f} at {code}"))
        for check in CHECKS:
            for s, _ in flag_windows(checks.status[check][:, i] == 2, max_gap=6, min_len=1):
                events.append(AnalysisEvent(s, i, "Telemetry consistency warning", "high",
                                            f"{CHECK_LABELS[check]} at {code}"))
        ranks = np.array([STATUS_RANK[str(x)] for x in trust.status[:, i]])
        for t in range(1, len(ranks)):
            if ranks[t] > ranks[t - 1]:
                status = trust.status[t, i]
                events.append(AnalysisEvent(t, i, "Telemetry trust degraded",
                                            "high" if status == "Contradicted" else "medium",
                                            f"Telemetry trust at {code} fell to {trust.score[t, i]:.2f} ({status})"))
    return sorted(events, key=lambda ev: (ev.tick, ev.seg_idx))
