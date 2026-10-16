"""
analyze_run: everything the analysis says about one run, from reported data only.
"""
from dataclasses import dataclass

import numpy as np

from app.analysis.consistency import ChecksResult, check_messages, run_checks
from app.analysis.frame import ReportedRun
from app.analysis.model import DetectorModel, persist_flags
from app.analysis.threshold import BaselineResult, baseline_alarms
from app.analysis.trust import TrustResult, compute_trust, trust_factors
from app.analysis.windows import AlertRecord, AnalysisEvent, analysis_events, build_alerts, segment_state


@dataclass
class AnalysisOutput:
    scores: np.ndarray  # (T, 6) 0..1
    ml_flag: np.ndarray  # (T, 6) bool
    checks: ChecksResult
    trust: TrustResult
    baseline: BaselineResult
    state: np.ndarray  # (T, 6) normal / anomalous / low_trust
    alerts: list[AlertRecord]
    events: list[AnalysisEvent]


def analyze_run(run: ReportedRun, model: DetectorModel) -> AnalysisOutput:
    scores = model.score(run)
    ml_flag = persist_flags(scores)
    checks = run_checks(run, model.reference)
    trust = compute_trust(run, checks)
    baseline = baseline_alarms(run, model.reference)
    state = segment_state(ml_flag, trust.status)

    def describe(seg_idx: int, tick: int) -> str | None:
        factors = trust_factors(run, model.reference, checks, trust, tick, seg_idx)
        if factors:
            return factors[0]["detail"]
        messages = check_messages(run, model.reference, checks, tick, seg_idx)
        return messages[0]["message"] if messages else None

    alerts = build_alerts(scores, ml_flag, trust, state, describe=describe)
    events = analysis_events(scores, ml_flag, checks, trust)
    return AnalysisOutput(scores, ml_flag, checks, trust, baseline, state, alerts, events)
