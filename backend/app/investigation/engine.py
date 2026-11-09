"""investigate(): grouping, evidence, scoring, decision, localisation and narrative for one run."""
from app.analysis.frame import ReportedRun
from app.analysis.pipeline import AnalysisOutput
from app.investigation import narrative as nar
from app.investigation.classify import decide, score_categories
from app.investigation.config import DEFAULT_CONFIG, EngineConfig
from app.investigation.evidence import collect
from app.investigation.grouping import group
from app.investigation.localise import localise
from app.investigation.types import Incident
from app.sim.topology import SEGMENT_CODES


def investigate(run: ReportedRun, out: AnalysisOutput, ref, cfg: EngineConfig = DEFAULT_CONFIG) -> list[Incident]:
    incidents: list[Incident] = []
    prev_end = -1
    for span in group(run, out.alerts, out.state, cfg):
        evidence, f = collect(run, out, ref, span, prev_end, cfg)
        prev_end = span.end
        cls, conf, label, hyps = decide(score_categories(f), cfg, evidence)
        loc = localise(cls, f, hyps)
        keys = set(span.windows)
        wins = [a for a in out.alerts if (a.seg_idx, a.start_tick, a.end_tick) in keys]
        open_evs = [run.events[i] for i in span.opening_events]
        starts = [w[1] for w in span.windows]
        detected = min(starts) if starts else min([e.tick for e in open_evs] + [span.start])
        segs = sorted({SEGMENT_CODES[w[0]] for w in span.windows} | {e.segment for e in open_evs if e.segment}
                      | {d.segment for d in span.departures}, key=SEGMENT_CODES.index)
        incidents.append(Incident(
            start_tick=span.start, end_tick=span.end, detected_tick=detected, segments=segs,
            classification=cls, confidence=conf, confidence_label=label, hypotheses=hyps, localisation=loc,
            severity=nar.severity(wins, cls, f, open_evs),
            summary=nar.summary(cls, f, loc, hyps), evidence=evidence, timeline=nar.timeline(evidence),
            chain=nar.chain(cls, f, evidence), mitre=nar.mitre(cls, f, evidence),
            actions=nar.actions(cls, loc, f, hyps),
            uncertainty=nar.uncertainty(hyps) if cls == "uncertain" else None,
            windows=[(SEGMENT_CODES[si], ws, we) for si, ws, we in span.windows]))
    return incidents
