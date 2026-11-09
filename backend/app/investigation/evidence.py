"""Evidence collection and derived facts for one incident span."""
from dataclasses import dataclass, field

import numpy as np

from app.analysis.consistency import CHECKS, WARN_Z, check_messages
from app.analysis.frame import ObservableEvent, ReportedRun
from app.analysis.pipeline import AnalysisOutput
from app.analysis.windows import CHECK_LABELS, FLAGGED_STATES
from app.investigation.signals import Departure
from app.investigation.types import EvidenceItem
from app.sim.topology import SEGMENT_CODES

_STATE_SUFFIXES = ("state changed", "stopped", "speed changed")
_SINGLE_VAR = ("implausible_change", "flatline", "range")


@dataclass
class Facts:
    flagged_segs: set[str] = field(default_factory=set)
    honest_change_segs: set[str] = field(default_factory=set)
    contradicted_segs: set[str] = field(default_factory=set)
    questioned_segs: set[str] = field(default_factory=set)  # trust below Supported on at least half of the span
    odd_one_out_segs: set[str] = field(default_factory=set)
    replay_segs: set[str] = field(default_factory=set)
    single_var_fault_segs: set[str] = field(default_factory=set)
    unauth_cmds: list[ObservableEvent] = field(default_factory=list)
    unauth_state: list[ObservableEvent] = field(default_factory=list)
    security_ws: bool = False
    reporting_change_segs: set[str] = field(default_factory=set)
    device_diag_segs: set[str] = field(default_factory=set)
    auth_cmds_near_onset: list[ObservableEvent] = field(default_factory=list)
    response_after_cmd: bool = False
    departures: list[Departure] = field(default_factory=list)
    pair_break_scores: np.ndarray = field(default_factory=lambda: np.zeros(5))
    span_ticks: int = 0
    honest_ticks: dict[str, int] = field(default_factory=dict)  # flagged tick count per honest-change segment


def _event_kind(e: ObservableEvent) -> str:
    if e.category == "control":
        return "equipment state" if e.event_type.endswith(_STATE_SUFFIXES) else "control event"
    if e.category == "security":
        return "security event"
    return "device event"


def _neighbours(i: int) -> list[int]:
    return [j for j in (i - 1, i + 1) if 0 <= j < len(SEGMENT_CODES)]


def collect(run: ReportedRun, out: AnalysisOutput, ref, span, prev_end: int, cfg) -> tuple[list[EvidenceItem], Facts]:
    T = run.n_ticks
    s, e = max(0, span.start), min(span.end, T - 1)
    sl = slice(s, e + 1)
    codes = SEGMENT_CODES
    idx = {c: i for i, c in enumerate(codes)}
    f = Facts(span_ticks=e - s + 1)

    state, flag, trust, checks = out.state[sl], out.ml_flag[sl], out.trust.status[sl], out.checks
    supported = trust == "Supported"
    # Missing readings ("insufficient") are neither a flag nor questioned trust.
    flagged = np.isin(state, FLAGGED_STATES)
    questioned = np.isin(trust, ("Review", "Contradicted"))
    for i, c in enumerate(codes):
        if flagged[:, i].any():
            f.flagged_segs.add(c)
        if (flag[:, i] & supported[:, i]).sum() >= 3:
            f.honest_change_segs.add(c)
            f.honest_ticks[c] = int(flagged[:, i].sum())
        if (trust[:, i] == "Contradicted").any():
            f.contradicted_segs.add(c)
        if questioned[:, i].sum() >= max(3, f.span_ticks // 2):
            f.questioned_segs.add(c)
        if checks.odd_one_out[sl, i].sum() >= 3:
            f.odd_one_out_segs.add(c)
        if (checks.status["replay"][sl, i] > 0).any():
            f.replay_segs.add(c)
        if any((checks.status[k][sl, i] > 0).any() for k in _SINGLE_VAR):
            f.single_var_fault_segs.add(c)

    for key in ("flow_balance", "pressure_gradient"):
        z = checks.pair_z[key][sl]
        for p in range(5):
            ok = supported[:, p] & supported[:, p + 1] & (np.abs(z[:, p]) >= WARN_Z)
            f.pair_break_scores[p] += float(np.abs(z[ok, p]).sum())

    lo = max(prev_end + 1, span.start - cfg.event_lookback_ticks)
    evs = [ev for ev in run.events if lo <= ev.tick <= span.end]
    for ev in evs:
        if ev.authorized == "no":
            (f.unauth_cmds if "command" in ev.event_type.lower() else f.unauth_state).append(ev)
        if ev.event_type == "Command from unregistered workstation":
            f.security_ws = True
        if ev.event_type == "Reporting configuration change" and ev.segment:
            f.reporting_change_segs.add(ev.segment)
        if ev.category == "device" and ev.segment:
            f.device_diag_segs.add(ev.segment)
    nonnormal = np.flatnonzero(flagged.any(axis=1))
    onset = s + int(nonnormal[0]) if nonnormal.size else s
    f.auth_cmds_near_onset = [ev for ev in run.events if ev.authorized == "yes" and "command" in ev.event_type.lower()
                              and onset - 12 <= ev.tick <= onset + 12]
    f.departures = list(span.departures)
    for cmd in f.unauth_cmds:
        if cmd.segment not in idx:
            continue
        ci = idx[cmd.segment]
        for j in [ci] + _neighbours(ci):
            if codes[j] not in f.honest_change_segs:
                continue
            hon = np.flatnonzero(out.ml_flag[:, j] & (out.trust.status[:, j] == "Supported"))
            if ((hon >= cmd.tick) & (hon <= cmd.tick + cfg.response_window_ticks)).any():
                f.response_after_cmd = True

    raw = []  # (tick, order, kwargs)
    for (si, ws, we) in span.windows:
        code = codes[si]
        a = next((x for x in out.alerts if x.seg_idx == si and x.start_tick == ws and x.end_tick == we), None)
        low = bool((out.state[ws:we + 1, si] == "low_trust").any())
        obs = a.summary if a and a.summary else f"{code} was flagged between ticks {ws} and {we}"
        if low:
            kind, sup = "trust drop", {"reporting_inconsistency": 0.3, "cyber_manipulation": 0.2, "sensor_fault": 0.2}
            interp = "Readings at this segment were not supported by neighbouring readings."
        else:
            kind, sup = "telemetry anomaly", {"physical_anomaly": 0.3, "sensor_fault": 0.2}
            interp = "Readings departed from the learned normal pattern in this window."
        raw.append((ws, 0, dict(kind=kind, tick=ws, end_tick=we, segment=code, observation=obs, interpretation=interp,
                                supports=sup, link={"type": "run", "tick": ws, "segment": code})))
    for i, c in enumerate(codes):
        for check in CHECKS:
            col = np.flatnonzero(checks.status[check][sl, i] > 0)
            if not col.size:
                continue
            t0 = s + int(col[0])
            msgs = [m for m in check_messages(run, ref, checks, t0, i) if m["check"] == check]
            obs = msgs[0]["message"] if msgs else CHECK_LABELS[check]
            if check == "replay":
                sup = {"cyber_manipulation": 0.4, "reporting_inconsistency": 0.2}
            elif check in _SINGLE_VAR:
                sup = {"sensor_fault": 0.3}
            else:
                sup = {"reporting_inconsistency": 0.2, "physical_anomaly": 0.2}
            raw.append((t0, 1, dict(kind="consistency check", tick=t0, end_tick=s + int(col[-1]), segment=c,
                                    observation=obs, interpretation=f"Consistency check: {CHECK_LABELS[check].lower()}.",
                                    supports=sup, link={"type": "run", "tick": t0, "segment": c})))
    for ev in evs:
        kind = _event_kind(ev)
        if ev.authorized == "no":
            sup = {"cyber_manipulation": 0.5}
            interp = "Unauthorized event coinciding with the incident window."
        else:
            sup = {"sensor_fault": 0.3} if kind == "device event" else {"normal_behaviour": 0.2}
            interp = "Logged event that coincides with the incident window."
        raw.append((ev.tick, 2, dict(kind=kind, tick=ev.tick, end_tick=ev.tick, segment=ev.segment,
                                     observation=ev.event_type + (f": {ev.details}" if ev.details else ""),
                                     interpretation=interp, supports=sup,
                                     link={"type": "event", "tick": ev.tick, "segment": ev.segment,
                                           "event_type": ev.event_type})))
    for d in span.departures:
        raw.append((d.start_tick, 3, dict(
            kind="setpoint departure", tick=d.start_tick, end_tick=d.end_tick, segment=d.segment,
            observation=f"Reported {d.equipment} at {d.observed_pct:.0f}% against an expected {d.expected_pct:.0f}%",
            interpretation="Equipment position differs from the last authorized command.",
            supports={"cyber_manipulation": 0.3}, link={"type": "run", "tick": d.start_tick, "segment": d.segment})))
    seg_idxs = {w[0] for w in span.windows}
    if seg_idxs and all(out.state[e, i] == "normal" and out.trust.status[e, i] == "Supported" for i in seg_idxs):
        raw.append((e, 4, dict(kind="recovery", tick=e, end_tick=e, segment=None,
                               observation="All affected segments are normal and supported at the end of the window",
                               interpretation="Readings returned to the learned normal pattern.",
                               supports={}, link={"type": "run", "tick": e, "segment": codes[min(seg_idxs)]})))
    raw.sort(key=lambda r: (r[0], r[1]))
    items = [EvidenceItem(id=f"E{n}", **kw) for n, (_, _, kw) in enumerate(raw, 1)]
    return items, f
