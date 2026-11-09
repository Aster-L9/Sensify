"""Segment and OT-layer localisation for the chosen category."""
from app.investigation.classify import reporting_segment
from app.investigation.evidence import Facts
from app.investigation.types import UNCERTAIN, Hypothesis, Localisation
from app.sim.topology import SEGMENT_CODES


def _loc(category: str, f: Facts) -> Localisation:
    if category == "cyber_manipulation":
        if f.unauth_cmds and f.unauth_cmds[0].segment:
            return Localisation(f.unauth_cmds[0].segment, ["control"], "")
        if f.replay_segs:
            return Localisation(sorted(f.replay_segs)[0], ["reporting"], "")
        chg = f.reporting_change_segs & (f.contradicted_segs | f.flagged_segs)
        if chg:
            return Localisation(sorted(chg)[0], ["reporting"], "")
        if f.departures:
            return Localisation(f.departures[0].segment, ["control"], "")
        return Localisation(None, [], "Not localised: no segment-level evidence of manipulation")
    if category == "reporting_inconsistency":
        seg = reporting_segment(f)
        if seg:
            return Localisation(seg, ["physical_process", "reporting"], "")
        return Localisation(None, [], "Not localised: no contradicted segment with an honestly changing neighbour")
    if category == "sensor_fault":
        if len(f.flagged_segs) == 1:
            return Localisation(next(iter(f.flagged_segs)), ["field_device"], "")
        return Localisation(None, [], "Not localised: more than one segment is flagged")
    if category == "physical_anomaly":
        pb = f.pair_break_scores
        order = sorted(range(5), key=lambda p: -pb[p])
        if pb[order[0]] > 0:
            best, nxt = order[0], order[1]
            if pb[nxt] >= 0.8 * pb[best]:
                a, b = sorted((SEGMENT_CODES[best + 1], SEGMENT_CODES[nxt + 1]))
                return Localisation(None, [], f"Evidence spans {a} and {b} about equally")
            return Localisation(SEGMENT_CODES[best + 1], ["physical_process"], "")
        if f.honest_ticks:
            ranked = sorted(f.honest_ticks.items(), key=lambda kv: (-kv[1], kv[0]))
            if len(ranked) > 1 and ranked[1][1] >= 0.8 * ranked[0][1]:
                a, b = sorted((ranked[0][0], ranked[1][0]))
                return Localisation(None, [], f"Evidence spans {a} and {b} about equally")
            return Localisation(ranked[0][0], ["physical_process"], "")
        return Localisation(None, [], "Not localised: no segment shows a supported change")
    if category == "normal_behaviour":
        for c in f.auth_cmds_near_onset:
            if c.segment:
                return Localisation(c.segment, ["control"], "")
        return Localisation(None, [], "Not localised: no commanded equipment")
    return Localisation(None, [], "Not localised")


def localise(category: str, f: Facts, hypotheses: list[Hypothesis]) -> Localisation:
    if category != UNCERTAIN:
        return _loc(category, f)
    locs = [_loc(h.category, f) for h in hypotheses[:2]]
    if len(locs) == 2 and locs[0].segment and locs[0].segment == locs[1].segment:
        return Localisation(locs[0].segment, locs[0].ot_layers, "")
    return Localisation(None, [], "Not localised: the leading explanations point to different places")
