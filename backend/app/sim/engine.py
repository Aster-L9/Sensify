"""
Run engine: simulates one run end to end.

Produces the actual process (ground truth), what the instruments report, the
event stream and the ground-truth labels. Independent RNG streams per concern
(environment, operator actions, measurement noise, scenario) let the engine
re-simulate a counterfactual run without the scenario for labelling.
"""
import math
from dataclasses import dataclass, field

import numpy as np

from app.sim.hydraulics import HydraulicInputs, solve_steady_state
from app.sim.scenarios import EXPECTED_ROOT_CAUSE, ScenarioConfig, envelope
from app.sim.topology import (
    LEAK_C_MAX, NOISE_SIGMA, P_DEL_NOM, P_SRC_NOM, PUMP_IDX, Q_NOM, SEGMENT_CODES, SEGMENTS,
    TICK_SECONDS, VALVE_IDX, segment_index,
)

N_SEG = len(SEGMENTS)
ALPHA_PQ = 1 - math.exp(-TICK_SECONDS / 10)
ALPHA_T = 1 - math.exp(-TICK_SECONDS / 60)
VALVE_RATE = 0.10  # max valve travel per tick (fraction of full stroke)
PUMP_RATE = 0.05  # max pump speed change per tick
COOLING_PER_KM = 0.04  # °C per km at nominal flow
T_INLET = 45.0

RNG_ENV, RNG_OPS, RNG_NOISE, RNG_SCENARIO = 1, 2, 3, 4

REPLAY_WINDOW = 24  # ticks of recorded pre-onset readings an attacker replays (2 min)
SENSOR_SCALE = {"pressure": (12.0, 10.0), "flow": (120.0, 100.0)}  # (erratic amplitude, drift) at magnitude 1
ROUNDING = {"pressure": 2, "flow": 1, "temperature": 2}
P_REPORTING_EVENT = 0.75  # chance a reporting-configuration change is logged
P_DEVICE_EVENT = 0.5  # chance a faulty sensor raises a device diagnostic
P_SECURITY_EVENT = 0.6  # chance the security monitor flags the unauthorized workstation


@dataclass
class SimEvent:
    tick: int
    segment: str | None
    source: str
    category: str  # control, security, device, process
    event_type: str
    authorized: str  # yes, no, unknown, n/a
    severity: str  # low, medium, high, critical
    details: str
    observable: bool


@dataclass
class GroundTruthSummary:
    scenario_type: str
    method: str | None
    target_segment: str | None
    event_start_tick: int | None
    event_peak_tick: int | None
    event_end_tick: int | None
    expected_root_cause: str
    manipulated_signal_or_asset: str
    notes: str


@dataclass
class RunData:
    config: ScenarioConfig
    n_ticks: int
    reported: dict[str, np.ndarray]  # pressure, flow, temperature, valve_open, pump_speed: (T, 6)
    actual: dict[str, np.ndarray]
    valve_state: np.ndarray  # (T, 6) str, reported
    equipment_state: np.ndarray  # (T, 6) str, reported
    phase: np.ndarray  # (T,) str
    is_target: np.ndarray  # (6,) bool
    process_affected: np.ndarray  # (T, 6) bool
    reporting_compromised: np.ndarray  # (T, 6) bool
    events: list[SimEvent]
    summary: GroundTruthSummary
    segment_codes: tuple[str, ...] = SEGMENT_CODES


@dataclass
class _Environment:
    p_src: np.ndarray
    p_del: np.ndarray
    t_in: np.ndarray


@dataclass
class _Controls:
    """Per-tick setpoints and process disturbances fed to the hydraulics."""
    valve_sp: np.ndarray
    pump_sp: np.ndarray
    p_src_off: np.ndarray
    p_del_off: np.ndarray
    leak_coeff: np.ndarray
    block_factor: np.ndarray
    leak_segment: int | None = None
    block_segment: int | None = None

    def copy(self) -> "_Controls":
        return _Controls(
            self.valve_sp.copy(), self.pump_sp.copy(), self.p_src_off.copy(), self.p_del_off.copy(),
            self.leak_coeff.copy(), self.block_factor.copy(), self.leak_segment, self.block_segment,
        )


@dataclass
class _Effects:
    """What a scenario changes: process controls, reporting overrides and events."""
    controls: _Controls | None = None  # None means the process is untouched
    events: list[SimEvent] = field(default_factory=list)
    hold_active: np.ndarray | None = None  # (T,) replay/conceal/stuck active at the target


def _ar1(rng, n: int, phi: float, sigma: float) -> np.ndarray:
    shocks = rng.normal(0.0, sigma, n)
    x = np.zeros(n)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + shocks[i]
    return x


def _environment(rng, n: int) -> _Environment:
    p_src0 = P_SRC_NOM + rng.uniform(-1.5, 1.5)
    p_del0 = P_DEL_NOM + rng.uniform(-1.5, 1.5)
    period = rng.uniform(8, 15) * 60 / TICK_SECONDS
    phase = rng.uniform(0, 2 * math.pi)
    t = np.arange(n)
    p_del = p_del0 + 0.5 * np.sin(2 * math.pi * t / period + phase) + _ar1(rng, n, 0.98, 0.05)
    p_src = p_src0 + _ar1(rng, n, 0.98, 0.03)
    t_in = T_INLET + rng.uniform(-0.5, 0.5) + _ar1(rng, n, 0.995, 0.02)
    return _Environment(p_src, p_del, t_in)


def _command(tick: int, segment: str, event_type: str, details: str, authorized: str = "yes",
             severity: str = "low", source: str = "Control Layer") -> SimEvent:
    return SimEvent(tick, segment, source, "control", event_type, authorized, severity, details, True)


def _operator_actions(rng, n: int) -> tuple[_Controls, list[SimEvent]]:
    """Routine authorized adjustments that are part of normal behaviour."""
    ones, zeros = np.ones(n), np.zeros(n)
    controls = _Controls(ones.copy(), ones.copy(), zeros.copy(), zeros.copy(), zeros.copy(), ones.copy())
    events: list[SimEvent] = []
    if rng.random() < 0.4:
        start, dur, value = int(rng.integers(24, n - 72)), int(rng.integers(24, 49)), rng.uniform(0.85, 0.95)
        end = min(start + dur, n - 1)
        controls.valve_sp[start:end] = value
        events.append(_command(start, "SEG-05", "Valve command issued", f"Operator sets valve V-12 to {value * 100:.0f}% open"))
        events.append(_command(end, "SEG-05", "Valve command issued", "Operator restores valve V-12 to 100% open"))
    if rng.random() < 0.3:
        start, dur, value = int(rng.integers(24, n - 72)), int(rng.integers(36, 61)), rng.uniform(0.93, 0.98)
        end = min(start + dur, n - 1)
        controls.pump_sp[start:end] = value
        events.append(_command(start, "SEG-03", "Pump command issued", f"Operator sets pump P-3 speed to {value * 100:.0f}%"))
        events.append(_command(end, "SEG-03", "Pump command issued", "Operator restores pump P-3 speed to 100%"))
    return controls, events


def _toward(current: float, target: float, rate: float) -> float:
    return current + max(-rate, min(rate, target - current))


def _temperature_profile(t_in: float, flow: np.ndarray) -> np.ndarray:
    temps = np.empty(N_SEG)
    t = t_in
    for i, seg in enumerate(SEGMENTS):
        t -= COOLING_PER_KM * seg.length_km * Q_NOM / max(flow[i], 100.0)
        temps[i] = t
    return temps


def _simulate_process(env: _Environment, ctl: _Controls, n: int) -> dict[str, np.ndarray]:
    p, q, temp = np.empty((n, N_SEG)), np.empty((n, N_SEG)), np.empty((n, N_SEG))
    valve, pump = np.empty(n), np.empty(n)
    v_pos, s_pos = ctl.valve_sp[0], ctl.pump_sp[0]
    for t in range(n):
        v_pos = _toward(v_pos, ctl.valve_sp[t], VALVE_RATE)
        s_pos = _toward(s_pos, ctl.pump_sp[t], PUMP_RATE)
        ss = solve_steady_state(HydraulicInputs(
            p_src=env.p_src[t] + ctl.p_src_off[t], p_del=env.p_del[t] + ctl.p_del_off[t],
            pump_speed=s_pos, valve_open=v_pos,
            leak_segment=ctl.leak_segment, leak_coeff=ctl.leak_coeff[t],
            block_segment=ctl.block_segment, block_factor=ctl.block_factor[t],
        ))
        t_ss = _temperature_profile(env.t_in[t], ss.flow)
        if t == 0:
            p[t], q[t], temp[t] = ss.pressure, ss.flow, t_ss
        else:
            p[t] = p[t - 1] + ALPHA_PQ * (ss.pressure - p[t - 1])
            q[t] = q[t - 1] + ALPHA_PQ * (ss.flow - q[t - 1])
            temp[t] = temp[t - 1] + ALPHA_T * (t_ss - temp[t - 1])
        valve[t], pump[t] = v_pos, s_pos
    valve_open = np.full((n, N_SEG), np.nan)
    pump_speed = np.full((n, N_SEG), np.nan)
    valve_open[:, VALVE_IDX] = valve * 100
    pump_speed[:, PUMP_IDX] = pump * 100
    return {"pressure": p, "flow": q, "temperature": temp, "valve_open": valve_open, "pump_speed": pump_speed}


def _ground_truth_event(tick: int, segment: str, source: str, category: str, event_type: str,
                        details: str, severity: str = "high") -> SimEvent:
    """An event only the simulator could know; never shown to the analysis."""
    return SimEvent(tick, segment, source, category, event_type, "n/a", severity, details, False)


def _scenario_effects(cfg: ScenarioConfig, rng, base: _Controls, n: int) -> _Effects:
    """Process changes and events for the scenario. Reporting overrides come later."""
    fx = _Effects()
    if cfg.scenario_type == "normal":
        return fx
    e = envelope(cfg)
    idx = segment_index(cfg.target_segment)
    seg, code, m, method = SEGMENTS[idx], cfg.target_segment, cfg.magnitude, cfg.method
    on = cfg.onset_tick
    hold_end = min(on + cfg.ramp_ticks + cfg.active_ticks, n)
    end = hold_end if cfg.recovery else n

    if cfg.scenario_type in ("physical_anomaly", "concealed_physical_incident"):
        ctl = base.copy()
        if method == "blockage":
            ctl.block_segment, ctl.block_factor = idx, 1 + 4 * m * e
            fx.events.append(_ground_truth_event(on, code, "Physical Process", "process", "Blockage forms",
                                                 f"A partial restriction develops in {seg.name}"))
            if cfg.recovery:
                fx.events.append(_ground_truth_event(hold_end, code, "Physical Process", "process",
                                                     "Blockage cleared", f"The restriction in {seg.name} clears", "low"))
        else:
            ctl.leak_segment, ctl.leak_coeff = idx, m * LEAK_C_MAX * e
            fx.events.append(_ground_truth_event(on, code, "Physical Process", "process", "Leak begins",
                                                 f"Product starts escaping in {seg.name}"))
            if cfg.recovery:
                fx.events.append(_ground_truth_event(hold_end, code, "Physical Process", "process",
                                                     "Leak isolated", f"The leak in {seg.name} is isolated", "low"))
        if cfg.scenario_type == "concealed_physical_incident":
            fx.events.append(_ground_truth_event(on, code, "Reporting Source", "security", "Reporting held near normal",
                                                 f"Reported values at {code} are held at normal-looking levels", "critical"))
        fx.controls = ctl

    elif cfg.scenario_type == "unauthorized_control":
        ctl = base.copy()
        if rng.random() < P_SECURITY_EVENT:
            fx.events.append(SimEvent(on, code, "Security Monitor", "security", "Command from unregistered workstation",
                                      "no", "high", "Engineering command originated from an unregistered workstation (10.0.4.23)", True))
        if method == "valve_close":
            final = 1 - 0.75 * m
            fx.events.append(_command(on, code, "Valve command issued",
                                      f"Command requests valve V-12 to move to {final * 100:.0f}% open", "no", "high"))
            for k in (1, 2, 3):
                t_k, setpoint = on + 2 * (k - 1), 1 - 0.75 * m * k / 3
                ctl.valve_sp[t_k:end] = setpoint
                fx.events.append(SimEvent(t_k + 1, code, "Valve V-12", "control", "Valve state changed", "no",
                                          "critical" if k == 3 else "high", f"Valve moves to {setpoint * 100:.0f}% open", True))
            restore = "Operator restores valve V-12 to 100% open"
            asset = "valve V-12"
        else:
            speed = 0.0 if method == "pump_stop" else 1 - 0.4 * m
            ctl.pump_sp[on:end] = speed
            if method == "pump_stop":
                fx.events.append(_command(on, code, "Pump trip command issued", "Command requests pump P-3 to stop", "no", "critical"))
                fx.events.append(SimEvent(on + 1, code, "Pump P-3", "control", "Pump stopped", "no", "critical", "Pump P-3 stops", True))
            else:
                fx.events.append(_command(on, code, "Pump command issued",
                                          f"Command requests pump P-3 speed {speed * 100:.0f}%", "no", "high"))
                fx.events.append(SimEvent(on + 1, code, "Pump P-3", "control", "Pump speed changed", "no", "high",
                                          f"Pump speed falls to {speed * 100:.0f}%", True))
            restore = "Operator restores pump P-3 to 100% speed"
            asset = "pump P-3"
        if cfg.recovery and hold_end < n:
            fx.events.append(_command(hold_end, code, "Valve command issued" if method == "valve_close" else "Pump command issued", restore))
        fx.events.append(_ground_truth_event(on, code, "Control Layer", "control", "Unauthorized control begins",
                                             f"Unauthorized commands drive {asset} away from its setpoint", "critical"))
        fx.controls = ctl

    elif cfg.scenario_type == "telemetry_manipulation":
        if rng.random() < P_REPORTING_EVENT:
            fx.events.append(SimEvent(on, code, "Reporting Source", "security", "Reporting configuration change",
                                      "unknown", "medium", f"Telemetry reporting configuration changed on the RTU at {code}", True))
        if method == "replay":
            ctl = base.copy()
            if seg.equipment == "inlet_control":
                ctl.p_src_off = -6 * m * e
            elif seg.equipment == "pump":
                ctl.pump_sp = np.minimum(base.pump_sp, 1 - 0.35 * m * e)
            elif seg.equipment == "valve":
                ctl.valve_sp = np.minimum(base.valve_sp, 1 - 0.7 * m * e)
            elif seg.equipment == "delivery_control":
                ctl.p_del_off = 5 * m * e
            fx.controls = ctl
            fx.events.append(_ground_truth_event(on, code, "Physical Process", "process", "Covert process change begins",
                                                 f"The process at {seg.name} is changed without a logged command"))
            fx.events.append(_ground_truth_event(on, code, "Reporting Source", "security", "Replay of recorded telemetry begins",
                                                 f"Recorded normal readings are replayed for {code}", "critical"))
        else:
            fx.events.append(_ground_truth_event(on, code, "Reporting Source", "security", "False offset injected",
                                                 f"A false offset is added to the reported pressure at {code}"))

    elif cfg.scenario_type == "sensor_fault":
        sensor = f"{cfg.variable.title()} Sensor"
        if rng.random() < P_DEVICE_EVENT:
            kind = {"erratic": "Erratic sensor reading", "stuck": "Sensor reading frozen", "drift": "Sensor calibration drift"}[method]
            fx.events.append(SimEvent(on + 2, code, sensor, "device", kind, "n/a", "medium",
                                      f"Device diagnostic from the {cfg.variable} sensor at {code}", True))
        fx.events.append(_ground_truth_event(on, code, sensor, "device", "Sensor fault begins",
                                             f"The {cfg.variable} sensor at {code} starts misreporting ({method})"))
    return fx


def _apply_reporting(cfg: ScenarioConfig, honest: dict[str, np.ndarray], rng):
    """Reporting-layer overrides at the target.

    Returns the reported values, the ticks where a hold (replay/conceal/stuck) is
    active, and the ticks where the reporting override is in force.
    """
    n = cfg.duration_ticks
    hold, window = np.zeros(n, dtype=bool), np.zeros(n, dtype=bool)
    if cfg.scenario_type not in ("sensor_fault", "telemetry_manipulation", "concealed_physical_incident"):
        return honest, hold, window

    rep = {k: v.copy() for k, v in honest.items()}
    e = envelope(cfg)
    idx = segment_index(cfg.target_segment)
    on, m = cfg.onset_tick, cfg.magnitude
    t = np.arange(n)
    span = (t >= on) & (t <= cfg.event_end_tick)
    length = min(REPLAY_WINDOW, on)

    if cfg.scenario_type == "sensor_fault":
        var = cfg.variable
        amplitude, drift = SENSOR_SCALE[var]
        digits = ROUNDING[var]
        window = e > 0
        if cfg.method == "erratic":
            spikes = rng.random(n) < 0.4
            signs = rng.choice([-1.0, 1.0], n)
            delta = np.where(window & spikes, signs * m * amplitude * e, 0.0)
            rep[var][:, idx] = np.round(honest[var][:, idx] + delta, digits)
        elif cfg.method == "stuck":
            rep[var][window, idx] = honest[var][on - 1, idx]
            hold = window.copy()
        else:
            grow = np.clip((t - on + 1) / max(cfg.ramp_ticks + cfg.active_ticks, 1), 0.0, 1.0)
            rep[var][:, idx] = np.round(honest[var][:, idx] + m * drift * grow * e, digits)

    elif cfg.scenario_type == "telemetry_manipulation":
        if cfg.method == "replay":
            window, hold = span, span.copy()
            for tick in np.flatnonzero(span):
                src = on - length + (tick - on) % length
                for var in rep:
                    rep[var][tick, idx] = honest[var][src, idx]
        else:
            window = e > 0
            sign = rng.choice([-1.0, 1.0])
            rep["pressure"][:, idx] = np.round(honest["pressure"][:, idx] + sign * 8 * m * e, 2)

    else:  # concealed physical incident: synthetic normal-looking values, not exact copies
        window, hold = span, span.copy()
        for var in ("pressure", "flow", "temperature"):
            mean = honest[var][on - length:on, idx].mean()
            noise = rng.normal(0.0, NOISE_SIGMA[var], int(span.sum()))
            rep[var][span, idx] = np.round(mean + noise, ROUNDING[var])

    return rep, hold, window


def _labels(cfg: ScenarioConfig, actual, counterfactual, reported, hold, window):
    """Ground-truth labels per tick and segment, plus the peak tick."""
    n = cfg.duration_ticks
    phase = np.full(n, "baseline", dtype=object)
    is_target = np.zeros(N_SEG, dtype=bool)
    sigma = NOISE_SIGMA
    process_affected = (
        (np.abs(actual["pressure"] - counterfactual["pressure"]) > 4 * sigma["pressure"])
        | (np.abs(actual["flow"] - counterfactual["flow"]) > 4 * sigma["flow"])
    )
    compromised = np.zeros((n, N_SEG), dtype=bool)
    if cfg.scenario_type == "normal":
        return phase, is_target, process_affected, compromised, None

    idx = segment_index(cfg.target_segment)
    is_target[idx] = True
    deviation = np.zeros(n, dtype=bool)
    reporting_effect = np.zeros(n)
    for var in ("pressure", "flow", "temperature"):
        diff = np.abs(reported[var][:, idx] - actual[var][:, idx]) / sigma[var]
        deviation |= diff > 4
        reporting_effect = np.maximum(reporting_effect, diff)
    compromised[:, idx] = window & (hold | deviation)

    process_effect = np.maximum(
        np.abs(actual["pressure"][:, idx] - counterfactual["pressure"][:, idx]) / sigma["pressure"],
        np.abs(actual["flow"][:, idx] - counterfactual["flow"][:, idx]) / sigma["flow"],
    )
    effect = process_effect if process_effect.max() > 0 else reporting_effect

    t = np.arange(n)
    on, ramp = cfg.onset_tick, cfg.ramp_ticks
    hold_end = min(on + ramp + cfg.active_ticks, n)
    active_end = hold_end if cfg.recovery else n
    phase[(t >= on) & (t < on + ramp)] = "onset"
    active = (t >= on + ramp) & (t < active_end)
    phase[active] = "active"
    if active.any() and effect[active].max() > 0:
        phase[active & (effect >= 0.9 * effect[active].max())] = "peak"
    if cfg.recovery:
        phase[(t >= hold_end) & (t <= cfg.event_end_tick)] = "recovery"
        phase[t > cfg.event_end_tick] = "recovered"
    window_ticks = (t >= on) & (t < active_end)
    peak_tick = int(np.argmax(np.where(window_ticks, effect, -1.0)))
    return phase, is_target, process_affected, compromised, peak_tick


def _summary(cfg: ScenarioConfig, peak_tick: int | None) -> GroundTruthSummary:
    if cfg.scenario_type == "normal":
        return GroundTruthSummary("normal", None, None, None, None, None, EXPECTED_ROOT_CAUSE["normal"],
                                  "None", "Normal fluctuating baseline")
    seg = SEGMENTS[segment_index(cfg.target_segment)]
    code, method, var = seg.code, cfg.method, cfg.variable
    asset, notes = {
        "physical_anomaly": (f"{seg.name} ({method})",
                             "Real leak with honest reporting; flow and pressure fall downstream" if method == "leak"
                             else "Partial restriction with honest reporting; flow falls along the line"),
        "sensor_fault": (f"{var.title()} sensor at {code} ({method})",
                         f"Reported {var} is {'erratic' if method == 'erratic' else 'frozen' if method == 'stuck' else 'drifting'} while the process is unchanged"),
        "telemetry_manipulation": (f"Reported telemetry at {code} (replayed)" if method == "replay" else f"Reported pressure at {code} (false offset)",
                                   "Recorded normal readings are replayed while the process is covertly changed" if method == "replay"
                                   else "A false offset is added to reported pressure; the process is unchanged"),
        "unauthorized_control": ("Valve V-12" if method == "valve_close" else "Pump P-3",
                                 "Unauthorized commands move the equipment; the process responds and reporting stays honest"),
        "concealed_physical_incident": (f"Reported telemetry at {code} (held near normal)",
                                        "Real leak while the target's reported values stay normal-looking"),
    }[cfg.scenario_type]
    return GroundTruthSummary(cfg.scenario_type, method, code, cfg.onset_tick, peak_tick, cfg.event_end_tick,
                              EXPECTED_ROOT_CAUSE[cfg.scenario_type], asset, notes)


def _report(actual: dict[str, np.ndarray], rng) -> dict[str, np.ndarray]:
    shape = actual["pressure"].shape
    noise = {var: rng.normal(0.0, NOISE_SIGMA[var], shape) for var in ("pressure", "flow", "temperature")}
    return {
        "pressure": np.round(actual["pressure"] + noise["pressure"], 2),
        "flow": np.round(actual["flow"] + noise["flow"], 1),
        "temperature": np.round(actual["temperature"] + noise["temperature"], 2),
        "valve_open": np.round(actual["valve_open"], 1),
        "pump_speed": np.round(actual["pump_speed"], 1),
    }


def _state_strings(reported: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    n = reported["pressure"].shape[0]
    valve_state = np.full((n, N_SEG), "Open", dtype=object)
    equipment_state = np.full((n, N_SEG), "Running", dtype=object)
    for t, pct in enumerate(reported["valve_open"][:, VALVE_IDX]):
        valve_state[t, VALVE_IDX] = "Open" if pct >= 99 else ("Closed" if pct < 5.5 else f"{pct:.0f}% Open")
    for t, pct in enumerate(reported["pump_speed"][:, PUMP_IDX]):
        equipment_state[t, PUMP_IDX] = "Stopped" if pct < 5 else "Running"
    return valve_state, equipment_state


def simulate_run(cfg: ScenarioConfig) -> RunData:
    n = cfg.duration_ticks
    rng_env = np.random.default_rng([cfg.seed, RNG_ENV])
    rng_ops = np.random.default_rng([cfg.seed, RNG_OPS])
    rng_noise = np.random.default_rng([cfg.seed, RNG_NOISE])
    rng_scn = np.random.default_rng([cfg.seed, RNG_SCENARIO])

    env = _environment(rng_env, n)
    base_controls, events = _operator_actions(rng_ops, n)
    effects = _scenario_effects(cfg, rng_scn, base_controls, n)

    counterfactual = _simulate_process(env, base_controls, n)
    actual = counterfactual if effects.controls is None else _simulate_process(env, effects.controls, n)
    honest = _report(actual, rng_noise)
    reported, hold, window = _apply_reporting(cfg, honest, rng_scn)
    valve_state, equipment_state = _state_strings(reported)
    phase, is_target, process_affected, compromised, peak_tick = _labels(
        cfg, actual, counterfactual, reported, hold, window)

    events = sorted(events + effects.events, key=lambda e: e.tick)
    return RunData(
        config=cfg,
        n_ticks=n,
        reported=reported,
        actual=actual,
        valve_state=valve_state,
        equipment_state=equipment_state,
        phase=phase,
        is_target=is_target,
        process_affected=process_affected,
        reporting_compromised=compromised,
        events=events,
        summary=_summary(cfg, peak_tick),
    )
