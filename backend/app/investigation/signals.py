import re
from dataclasses import dataclass

import numpy as np

from app.analysis.frame import ObservableEvent, ReportedRun
from app.investigation.config import EngineConfig
from app.sim.topology import PUMP_IDX, SEGMENT_CODES, VALVE_IDX

_DIGITS = re.compile(r"\d+")


def _percentages(text: str) -> list[str]:
    """Every whole number written directly before a "%" sign, in order."""
    return [m.group() for m in _DIGITS.finditer(text) if text.startswith("%", m.end())]

# equipment key -> (segment index, ReportedRun attribute)
EQUIPMENT = {"valve": (VALVE_IDX, "valve_open"), "pump": (PUMP_IDX, "pump_speed")}


@dataclass
class Departure:
    segment: str
    equipment: str
    start_tick: int
    end_tick: int
    expected_pct: float
    observed_pct: float


def is_opening_event(e: ObservableEvent) -> bool:
    return e.authorized == "no" or e.category in ("security", "device")


def _equipment_of(e: ObservableEvent) -> str | None:
    if e.event_type == "Valve command issued":
        return "valve"
    if e.event_type == "Pump command issued":
        return "pump"
    return None


def setpoint_departures(run: ReportedRun, cfg: EngineConfig) -> list[Departure]:
    n = run.n_ticks
    out: list[Departure] = []
    for equip, (idx, attr) in EQUIPMENT.items():
        setpoint = np.full(n, 100.0)
        ignore = np.zeros(n, dtype=bool)
        cmds = sorted((e for e in run.events if e.authorized == "yes" and _equipment_of(e) == equip
                       and 0 <= e.tick < n), key=lambda e: e.tick)
        for e in cmds:
            m = _percentages(e.details or "")
            if not m:
                continue
            setpoint[e.tick:] = float(m[-1])
            ignore[e.tick:e.tick + cfg.setpoint_settle_ticks] = True
        values = getattr(run, attr)[:, idx]
        dev = (np.abs(values - setpoint) > cfg.setpoint_tol_pct) & ~ignore  # NaN compares False
        t = 0
        while t < n:
            if not dev[t]:
                t += 1
                continue
            s = t
            while t < n and dev[t]:
                t += 1
            if t - s >= cfg.setpoint_min_ticks:
                out.append(Departure(SEGMENT_CODES[idx], equip, s, t - 1, float(setpoint[s]), float(values[s])))
    return sorted(out, key=lambda d: d.start_tick)


def unauthorized_spans(run: ReportedRun) -> list[tuple[str, int, int]]:
    spans = []
    for e in run.events:
        equip = _equipment_of(e)
        if e.authorized != "no" or equip is None:
            continue
        seg = SEGMENT_CODES[EQUIPMENT[equip][0]]
        end = run.n_ticks - 1
        for r in sorted(run.events, key=lambda x: x.tick):
            if r.tick > e.tick and r.authorized == "yes" and _equipment_of(r) == equip:
                end = r.tick
                break
        spans.append((seg, e.tick, end))
    return spans
