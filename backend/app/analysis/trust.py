"""
Telemetry trust (spec §5.5): are the reported values believable?

Trust is separate from anomaly: an unauthorized valve closure is anomalous but its
readings are trusted. Each factor subtracts weight × severity from 1; the result is
smoothed with an EMA and mapped to Supported / Review / Contradicted.

Missing readings are neither support nor contradiction. Where a segment's own pressure or
flow is missing, too few of its recent readings arrived, or no neighbour reported to
cross-check it, the outcome is Insufficient with no score (Sprint 03 handover DH-08).
"""
from dataclasses import dataclass, field

import numpy as np

from app.analysis.consistency import ChecksResult, check_messages
from app.analysis.frame import ReportedRun
from app.analysis.reference import ReferenceProfile
from app.sim.topology import SEGMENT_CODES, TICK_SECONDS

TRUST_WEIGHTS = {
    "neighbour_strong": 0.45,
    "neighbour_weak": 0.20,
    "implausible": 0.35,
    "replay": 0.60,
    "flatline": 0.25,
    "reporting_event": 0.25,
}
SUPPORTED_MIN, REVIEW_MIN = 0.70, 0.40
EMA_ALPHA = 0.5
REPORTING_EVENT_TICKS = 60  # a reporting-configuration change counts for 5 minutes
REPORTING_EVENT_TYPE = "Reporting configuration change"
INSUFFICIENT = "Insufficient"
RECENT_TICKS = 6  # 30 s: a segment needs at least MIN_RECENT of its last RECENT_TICKS readings
MIN_RECENT = 4

FACTOR_LABELS = {
    "replay": "Replayed readings",
    "neighbour_strong": "Disagrees with both neighbouring segments",
    "neighbour_weak": "Disagrees with a neighbouring segment",
    "implausible": "Physically implausible change",
    "flatline": "Unnaturally flat readings",
    "reporting_event": "Reporting configuration changed",
}
FACTOR_CHECKS = {
    "replay": ("replay",),
    "neighbour_strong": ("flow_balance", "pressure_gradient"),
    "neighbour_weak": ("flow_balance", "pressure_gradient"),
    "implausible": ("implausible_change", "range"),
    "flatline": ("flatline",),
}


INSUFFICIENT_LABELS = {
    "missing": "Reading missing",
    "stale": "Readings arriving intermittently",
    "no_neighbour": "No neighbouring readings to cross-check",
}


@dataclass
class TrustResult:
    score: np.ndarray  # (T, 6) 0..1; NaN where the evidence is insufficient
    status: np.ndarray  # (T, 6) Supported / Review / Contradicted / Insufficient
    raw_penalties: dict[str, np.ndarray]  # factor -> (T, 6) weight × severity
    gaps: dict[str, np.ndarray] = field(default_factory=dict)  # missing / stale / no_neighbour -> (T, 6) bool

    @property
    def insufficient(self) -> np.ndarray:
        return self.status == INSUFFICIENT


def trust_status(score: np.ndarray, insufficient: np.ndarray | None = None) -> np.ndarray:
    status = np.where(score >= SUPPORTED_MIN, "Supported", np.where(score >= REVIEW_MIN, "Review", "Contradicted"))
    return status if insufficient is None else np.where(insufficient, INSUFFICIENT, status)


def evidence_gaps(run: ReportedRun) -> dict[str, np.ndarray]:
    """Where there is not enough reported evidence to judge a segment's readings, by reason."""
    missing = np.isnan(run.pressure) | np.isnan(run.flow)
    arrived = (~missing).astype(int)
    recent = np.zeros_like(arrived)
    for lag in range(min(RECENT_TICKS, len(arrived))):  # a live run may have fewer ticks so far
        recent[lag:] += arrived[:len(arrived) - lag]
    window = np.minimum(np.arange(run.n_ticks) + 1, RECENT_TICKS)[:, None]
    stale = ~missing & (window - recent > RECENT_TICKS - MIN_RECENT)
    no_neighbour = np.zeros_like(missing)
    for i in range(len(SEGMENT_CODES)):
        neighbours = [j for j in (i - 1, i + 1) if 0 <= j < len(SEGMENT_CODES)]
        no_neighbour[:, i] = ~missing[:, i] & missing[:, neighbours].all(axis=1)
    return {"missing": missing, "stale": stale, "no_neighbour": no_neighbour}


def _severity(level: np.ndarray) -> np.ndarray:
    return np.where(level >= 2, 1.0, np.where(level == 1, 0.5, 0.0))


def _reporting_event_mask(run: ReportedRun) -> np.ndarray:
    mask = np.zeros((run.n_ticks, len(SEGMENT_CODES)), dtype=bool)
    for e in run.events:
        if e.event_type == REPORTING_EVENT_TYPE and e.authorized in ("unknown", "no") and e.segment in SEGMENT_CODES:
            mask[e.tick:e.tick + REPORTING_EVENT_TICKS, SEGMENT_CODES.index(e.segment)] = True
    return mask


def compute_trust(run: ReportedRun, checks: ChecksResult) -> TrustResult:
    s = checks.status
    pair_sev = _severity(np.maximum(s["flow_balance"], s["pressure_gradient"]))
    penalties = {
        "neighbour_strong": np.where(checks.odd_one_out, TRUST_WEIGHTS["neighbour_strong"] * pair_sev, 0.0),
        "neighbour_weak": np.where(checks.one_sided, TRUST_WEIGHTS["neighbour_weak"] * pair_sev, 0.0),
        "implausible": TRUST_WEIGHTS["implausible"] * _severity(np.maximum(s["implausible_change"], s["range"])),
        "replay": TRUST_WEIGHTS["replay"] * _severity(s["replay"]),
        "flatline": TRUST_WEIGHTS["flatline"] * _severity(s["flatline"]),
        "reporting_event": np.where(_reporting_event_mask(run), TRUST_WEIGHTS["reporting_event"], 0.0),
    }
    gaps = evidence_gaps(run)
    insufficient = gaps["missing"] | gaps["stale"] | gaps["no_neighbour"]
    raw = np.clip(1.0 - sum(penalties.values()), 0.0, 1.0)
    raw[insufficient] = np.nan
    score = np.empty_like(raw)
    score[0] = raw[0]
    for t in range(1, run.n_ticks):
        # The EMA restarts when evidence returns, so a gap never reads as support or as contradiction.
        score[t] = np.where(np.isnan(score[t - 1]), raw[t], EMA_ALPHA * raw[t] + (1 - EMA_ALPHA) * score[t - 1])
    return TrustResult(score=score, status=trust_status(score, insufficient), raw_penalties=penalties, gaps=gaps)


def _gap_detail(run: ReportedRun, reason: str, tick: int, seg_idx: int) -> str:
    code = SEGMENT_CODES[seg_idx]
    secs = tick * TICK_SECONDS
    at = f"T+{secs // 60:02d}:{secs % 60:02d}"
    if reason == "missing":
        absent = [v for v, arr in (("pressure", run.pressure), ("flow", run.flow)) if np.isnan(arr[tick, seg_idx])]
        return f"No {' or '.join(absent)} reading from {code} at {at}, so its trust cannot be judged"
    if reason == "stale":
        lo = max(0, tick - RECENT_TICKS + 1)
        got = int((~(np.isnan(run.pressure[lo:tick + 1, seg_idx]) | np.isnan(run.flow[lo:tick + 1, seg_idx]))).sum())
        return f"Only {got} of the last {tick - lo + 1} readings from {code} arrived, too few to judge its trust"
    return f"No neighbouring segment reported at {at}, so readings at {code} cannot be cross-checked"


def trust_factors(run: ReportedRun, ref: ReferenceProfile, checks: ChecksResult, trust: TrustResult,
                  tick: int, seg_idx: int) -> list[dict]:
    """The factors lowering trust at this tick and segment, strongest first, in plain language.

    Where the evidence is insufficient the only factors are the reasons why."""
    if trust.gaps and trust.status[tick, seg_idx] == INSUFFICIENT:
        return [{"code": "insufficient", "label": INSUFFICIENT_LABELS[reason], "weight": 0.0, "penalty": 0.0,
                 "detail": _gap_detail(run, reason, tick, seg_idx)}
                for reason in ("missing", "stale", "no_neighbour") if trust.gaps[reason][tick, seg_idx]]
    messages = None
    factors = []
    for code, penalty in trust.raw_penalties.items():
        value = float(penalty[tick, seg_idx])
        if value <= 0:
            continue
        if code == "reporting_event":
            event = next((e for e in reversed(run.events) if e.event_type == REPORTING_EVENT_TYPE
                          and e.segment == SEGMENT_CODES[seg_idx] and e.tick <= tick), None)
            secs = (event.tick if event else tick) * TICK_SECONDS
            detail = (f"{REPORTING_EVENT_TYPE} at T+{secs // 60:02d}:{secs % 60:02d} "
                      f"(authorization {event.authorized if event else 'unknown'})")
        else:
            if messages is None:
                messages = check_messages(run, ref, checks, tick, seg_idx)
            detail = next((m["message"] for m in messages if m["check"] in FACTOR_CHECKS[code]), FACTOR_LABELS[code])
        factors.append({"code": code, "label": FACTOR_LABELS[code], "weight": TRUST_WEIGHTS[code],
                        "penalty": round(value, 3), "detail": detail})
    factors.sort(key=lambda f: (-f["weight"], f["code"]))
    for f in factors:
        if f["code"].startswith("neighbour"):
            f["code"] = "neighbour"
    return factors
