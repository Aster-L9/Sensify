"""
Pipeline topology and physical constants shared by the simulator and the analysis.

Flow runs SEG-01 -> SEG-06. Each segment's instruments read at the segment outlet.
Nominal values are at Q_NOM with the valve fully open and the pump at 100 %.
"""
from dataclasses import dataclass

TICK_SECONDS = 5

Q_NOM = 830.0  # m³/h
P_SRC_NOM = 78.0  # bar, inlet header pressure
P_DEL_NOM = 62.0  # bar, delivery pressure at the Jubail outlet

PUMP_SHUTOFF_HEAD = 7.0  # bar at zero flow, full speed
PUMP_NOM_HEAD = 4.5  # bar at Q_NOM, full speed
VALVE_NOM_DROP = 0.6  # bar across the fully open valve at Q_NOM
LEAK_C_MAX = 23.1  # leak coefficient at magnitude 1 (≈ 25 % of flow)

NOISE_SIGMA = {"pressure": 0.08, "flow": 1.5, "temperature": 0.05}


@dataclass(frozen=True)
class SegmentSpec:
    code: str
    name: str
    segment_type: str
    order: int
    length_km: float
    nominal_drop_bar: float
    diameter_mm: float
    design_pressure_bar: float
    equipment: str | None
    lat_start: float
    lon_start: float
    lat_end: float
    lon_end: float
    flow_meter: str = "outlet"  # the inlet terminal's receipt meter sits at its inlet


SEGMENTS: tuple[SegmentSpec, ...] = (
    SegmentSpec("SEG-01", "Dhahran Terminal", "terminal", 0, 5.8, 1.0, 1067, 96.5,
                "inlet_control", 26.2361, 50.0393, 26.2861, 50.0593, flow_meter="inlet"),
    SegmentSpec("SEG-02", "Pipeline Corridor A", "pipeline", 1, 12.3, 3.0, 914, 82.7,
                None, 26.2861, 50.0593, 26.3900, 50.0800),
    SegmentSpec("SEG-03", "Pump Station Alpha", "pump_station", 2, 3.5, 0.5, 914, 103.4,
                "pump", 26.3900, 50.0800, 26.4200, 50.0950),
    SegmentSpec("SEG-04", "Pipeline Corridor B", "pipeline", 3, 15.7, 4.0, 914, 82.7,
                None, 26.4200, 50.0950, 26.5500, 50.1000),
    SegmentSpec("SEG-05", "Valve Station V-12", "valve_station", 4, 3.4, 0.4, 914, 82.7,
                "valve", 26.5500, 50.1000, 26.5800, 50.1050),
    SegmentSpec("SEG-06", "Jubail Industrial Terminal", "terminal", 5, 48.2, 11.0, 1219, 96.5,
                "delivery_control", 26.5800, 50.1050, 26.9600, 49.6600),
)

SEGMENT_CODES: tuple[str, ...] = tuple(s.code for s in SEGMENTS)
PUMP_IDX = 2
VALVE_IDX = 4


def segment_index(code: str) -> int:
    return SEGMENT_CODES.index(code)
