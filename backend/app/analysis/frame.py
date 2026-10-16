"""
What the analysis is allowed to see of a run: reported telemetry and observable events.

Converters that build a ReportedRun live outside this package (the scoring service
and the ML dataset loader) so nothing here can reach ground truth.
"""
from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class ObservableEvent:
    tick: int
    segment: str | None
    source: str
    category: str
    event_type: str
    authorized: str
    severity: str


@dataclass
class ReportedRun:
    """Reported values per tick and segment, in SEGMENT_CODES order. NaN where a segment has no valve/pump."""
    pressure: np.ndarray  # (T, 6) bar
    flow: np.ndarray  # (T, 6) m³/h
    temperature: np.ndarray  # (T, 6) °C
    valve_open: np.ndarray  # (T, 6) %
    pump_speed: np.ndarray  # (T, 6) %
    events: list[ObservableEvent] = field(default_factory=list)

    @property
    def n_ticks(self) -> int:
        return self.pressure.shape[0]
