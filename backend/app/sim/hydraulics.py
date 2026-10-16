"""
Quasi-steady hydraulic model of the six-segment chain.

Pressures are marched from the inlet header through each segment for a trial
upstream flow; the flow is bisected until the outlet matches the delivery pressure.
"""
import math
from dataclasses import dataclass

import numpy as np

from app.sim.topology import (
    SEGMENTS, Q_NOM, PUMP_SHUTOFF_HEAD, PUMP_NOM_HEAD, VALVE_NOM_DROP,
)

_K = [s.nominal_drop_bar / Q_NOM ** 2 for s in SEGMENTS]
_H2 = (PUMP_SHUTOFF_HEAD - PUMP_NOM_HEAD) / Q_NOM ** 2
_KV = VALVE_NOM_DROP / Q_NOM ** 2


@dataclass
class HydraulicInputs:
    p_src: float
    p_del: float
    pump_speed: float = 1.0
    valve_open: float = 1.0
    leak_segment: int | None = None
    leak_coeff: float = 0.0
    block_segment: int | None = None
    block_factor: float = 1.0


@dataclass
class HydraulicState:
    pressure: np.ndarray  # (6,) bar at each segment outlet
    flow: np.ndarray  # (6,) m³/h through each segment outlet
    leak_flow: float


def _march(inp: HydraulicInputs, q_up: float):
    p, q = inp.p_src, q_up
    pressure, flow = np.empty(len(SEGMENTS)), np.empty(len(SEGMENTS))
    leak_flow = 0.0
    for i, seg in enumerate(SEGMENTS):
        k = _K[i] * (inp.block_factor if i == inp.block_segment else 1.0)
        q_in = q
        if i == inp.leak_segment and inp.leak_coeff > 0:
            p_mid = p - k / 2 * q * q
            leak_flow = inp.leak_coeff * math.sqrt(max(p_mid, 0.0))
            q = max(q - leak_flow, 0.0)
            p = p_mid - k / 2 * q * q
        else:
            p -= k * q * q
        if seg.equipment == "pump":
            p += inp.pump_speed ** 2 * PUMP_SHUTOFF_HEAD - _H2 * q * q
        elif seg.equipment == "valve":
            p -= _KV / max(inp.valve_open, 0.05) ** 2 * q * q
        # The inlet terminal meters what it receives; every other meter sits at the outlet.
        pressure[i], flow[i] = p, (q_in if seg.flow_meter == "inlet" else q)
    return p, pressure, flow, leak_flow


def solve_steady_state(inp: HydraulicInputs) -> HydraulicState:
    lo, hi = 0.0, 2000.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if _march(inp, mid)[0] > inp.p_del:
            lo = mid
        else:
            hi = mid
    _, pressure, flow, leak_flow = _march(inp, (lo + hi) / 2)
    return HydraulicState(pressure=pressure, flow=flow, leak_flow=leak_flow)
