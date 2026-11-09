from dataclasses import dataclass, field

import numpy as np

from app.analysis.frame import ReportedRun
from app.analysis.windows import AlertRecord, flag_windows
from app.investigation.config import EngineConfig
from app.investigation.signals import Departure, is_opening_event, setpoint_departures, unauthorized_spans
from app.sim.topology import SEGMENT_CODES


@dataclass
class Span:
    start: int
    end: int
    windows: list[tuple[int, int, int]] = field(default_factory=list)  # (seg_idx, start, end)
    opening_events: list[int] = field(default_factory=list)  # indexes into run.events
    departures: list[Departure] = field(default_factory=list)


def group(run: ReportedRun, alerts: list[AlertRecord], state: np.ndarray, cfg: EngineConfig,
          use_events: bool = True) -> list[Span]:
    seg_idx = {c: i for i, c in enumerate(SEGMENT_CODES)}
    deps = setpoint_departures(run, cfg) if use_events else []
    unauth = unauthorized_spans(run) if use_events else []
    # items: (start, end, seg_idx | None, kind, payload)
    items = [(a.start_tick, a.end_tick, a.seg_idx, "window", a) for a in alerts]
    if use_events:
        for i, e in enumerate(run.events):
            if is_opening_event(e):
                items.append((e.tick, e.tick, seg_idx.get(e.segment), "event", i))
        for d in deps:
            items.append((d.start_tick, d.end_tick, seg_idx[d.segment], "departure", d))
    items.sort(key=lambda it: (it[0], it[1]))

    def open_condition(seg: int | None, end: int) -> bool:
        if not use_events or seg is None:
            return False
        code = SEGMENT_CODES[seg]
        if end < state.shape[0] and state[end, seg] == "low_trust":
            return True
        if any(s == code and a <= end <= b for s, a, b in unauth):
            return True
        return any(d.segment == code and d.start_tick <= end <= d.end_tick for d in deps)

    spans: list[Span] = []
    reach = -1
    for start, end, seg, kind, payload in items:
        if spans and start <= reach:
            span = spans[-1]
            span.end = max(span.end, end)
        else:
            span = Span(start, end)
            spans.append(span)
            reach = -1
        item_reach = (span.end if open_condition(seg, end) else end) + cfg.gap_ticks
        reach = max(reach, item_reach)
        if kind == "window":
            span.windows.append((payload.seg_idx, payload.start_tick, payload.end_tick))
        elif kind == "event":
            span.opening_events.append(payload)
        else:
            span.departures.append(payload)
    return spans


def group_flags(flags: np.ndarray, cfg: EngineConfig) -> list[tuple[int, int]]:
    wins = sorted(w for i in range(flags.shape[1]) for w in flag_windows(flags[:, i]))
    merged: list[list[int]] = []
    for s, e in wins:
        if merged and s <= merged[-1][1] + cfg.gap_ticks:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]
