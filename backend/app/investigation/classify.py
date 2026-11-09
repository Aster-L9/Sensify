"""Rule scoring of the five categories and the decision rule (including Uncertain)."""
from app.investigation.evidence import Facts
from app.investigation.types import CATEGORIES, UNCERTAIN, Hypothesis
from app.sim.topology import SEGMENT_CODES


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def _nbrs(code: str) -> set[str]:
    i = SEGMENT_CODES.index(code)
    return {SEGMENT_CODES[j] for j in (i - 1, i + 1) if 0 <= j < len(SEGMENT_CODES)}


def reporting_segment(f: Facts) -> str | None:
    """A contradicted (or persistently questioned) odd-one-out segment with an honestly changing neighbour."""
    for x in sorted((f.contradicted_segs | f.questioned_segs) & f.odd_one_out_segs):
        if _nbrs(x) & f.honest_change_segs:
            return x
    return None


def score_categories(f: Facts) -> dict[str, float]:
    cyber = 0.0
    cyber += 0.60 if f.unauth_cmds else 0
    cyber += 0.20 if f.unauth_state else 0
    cyber += 0.20 if f.response_after_cmd else 0
    cyber += 0.15 if f.security_ws else 0
    cyber += 0.60 if f.replay_segs else 0
    cyber += 0.35 if f.reporting_change_segs & (f.contradicted_segs | f.flagged_segs) else 0
    cyber += 0.25 if f.departures else 0

    rep = 0.0
    rep += 0.80 if reporting_segment(f) else 0
    rep -= 0.40 if f.replay_segs else 0
    rep -= 0.30 if f.reporting_change_segs else 0

    sensor = 0.0
    if len(f.flagged_segs) == 1:
        seg = next(iter(f.flagged_segs))
        sensor += 0.40
        sensor += 0.30 if seg in f.single_var_fault_segs else 0
        sensor += 0.20 if seg in f.device_diag_segs else 0
        sensor -= 0.40 if f.honest_change_segs - {seg} else 0
    sensor -= 0.30 if f.unauth_cmds else 0

    phys = 0.0
    phys += 0.40 if f.honest_change_segs and not f.contradicted_segs else 0
    phys += 0.20 if len(f.honest_change_segs) >= 2 else 0
    phys += 0.20 if f.pair_break_scores.max() > 0 else 0
    phys -= 0.50 if f.unauth_cmds else 0
    phys -= 0.30 if f.auth_cmds_near_onset else 0

    norm = 0.0
    if any(c.segment and ({c.segment} | _nbrs(c.segment)) & f.flagged_segs for c in f.auth_cmds_near_onset):
        norm += 0.60
    norm += 0.20 if f.span_ticks <= 24 and not f.contradicted_segs else 0
    norm -= 0.60 if (f.unauth_cmds or f.contradicted_segs or f.replay_segs) else 0

    raw = {"physical_anomaly": phys, "sensor_fault": sensor, "cyber_manipulation": cyber,
           "reporting_inconsistency": rep, "normal_behaviour": norm}
    return {k: _clip(raw[k]) for k in CATEGORIES}


def decide(scores: dict[str, float], cfg, evidence=None) -> tuple[str, float, str, list[Hypothesis]]:
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_c, top = ranked[0]
    second = ranked[1][1]
    conf = round(min(1.0, top * (0.6 + 0.4 * min(1.0, (top - second) / 0.3))), 2)
    label = "Low" if conf < 0.5 else "Moderate" if conf < 0.75 else "High"
    hyps = []
    for c, sc in ranked[:3]:
        ids = [e.id for e in (evidence or []) if e.supports.get(c, 0) > 0]
        hyps.append(Hypothesis(c, round(sc, 2), ids))
    # Rounded so a nominal boundary score counts as on the boundary: 0.60 - 0.45 is 0.1499... in floating point.
    uncertain = round(top, 9) < cfg.min_score or round(top - second, 9) < cfg.margin
    return (UNCERTAIN if uncertain else top_c), conf, label, hyps
