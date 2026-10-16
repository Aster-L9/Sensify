"""
Seeded mock-dataset generator.

Runs the simulator the live app uses (`app.sim.engine.simulate_run`) over a fixed
plan of normal and scenario runs and writes, into one directory:

- runs.csv          one row per run: split, scenario parameters, seed, start time
- telemetry.csv.gz  one row per run x tick x segment: actual and reported values, labels
- events.csv        control, security, device and process events, with the observable flag
- ground_truth.csv  one row per run: scenario summary and event ticks
- DATA_CARD.md      settings, split table, value ranges, event counts, calibration check

Splits are by run, so no run contributes to two splits. The same seed regenerates
the same files.

CLI (from backend/):  python -m ml.generate_dataset --out ml/data --seed 2026 [--small]
"""
from __future__ import annotations

import argparse
import inspect
import json
import numbers
import shlex
import time
from datetime import datetime, timedelta
from itertools import zip_longest
from pathlib import Path

import numpy as np
import pandas as pd

from app.sim.engine import RunData, simulate_run
from app.sim.scenarios import CATALOG, RECOVERY_MIN, SCENARIO_TYPES, ScenarioConfig, validate_config
from app.sim.topology import SEGMENTS, TICK_SECONDS

SPLITS = ("train", "validation", "test")
FAULT_TYPES = tuple(t for t in SCENARIO_TYPES if t != "normal")
_CATALOG = {t["id"]: t for t in CATALOG}
SENSOR_VARIABLES = ("pressure", "flow")
PLAYBACK_SPEED = 10
DURATION_MIN = 20
RAMP_MIN = 1
START_TIME = datetime(2026, 9, 1)
RUN_SPACING = timedelta(hours=1)
SEED_SPACE = 1_000_000
SMALL_PLAN = {"n_train_normal": 4, "n_val_normal": 2, "n_val_scenario": 5, "n_test_normal": 2, "n_test_scenario": 10}
BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = BACKEND_DIR / "ml" / "data"

RUNS_COLUMNS = [
    "run_id", "split", "scenario_type", "method", "target_segment", "variable", "magnitude", "onset_min",
    "ramp_min", "active_min", "recovery", "duration_min", "seed", "start_time",
]
TELEMETRY_COLUMNS = [
    "timestamp", "run_id", "segment_id", "tick", "scenario_phase",
    "actual_pressure_bar", "reported_pressure_bar", "actual_flow_m3h", "reported_flow_m3h",
    "actual_temperature_c", "reported_temperature_c", "valve_state",
    "reported_valve_open_pct", "actual_valve_open_pct", "reported_pump_speed_pct", "actual_pump_speed_pct",
    "equipment_state", "is_target", "process_affected", "reporting_compromised",
]
EVENTS_COLUMNS = [
    "event_id", "timestamp", "run_id", "tick", "segment_id", "event_source", "category", "event_type",
    "authorized", "severity", "details", "observable",
]
GROUND_TRUTH_COLUMNS = [
    "run_id", "scenario_type", "method", "target_segment", "event_start", "event_peak", "event_end",
    "event_start_tick", "event_peak_tick", "event_end_tick", "expected_root_cause",
    "manipulated_signal_or_asset", "ground_truth_notes",
]
DATA_FILES = ("runs.csv", "telemetry.csv.gz", "events.csv", "ground_truth.csv")
EVENT_CATEGORIES = ("control", "security", "device", "process")

# Calibration against the mock-data workbook.
FLOW_RANGE = (780.0, 880.0)  # m³/h; the workbook's baseline flows are 800–853
PRESSURE_RANGE = (68.0, 78.0)  # bar; the workbook's baseline pressures are 69.8–73.2
PRESSURE_CHECKED = ("SEG-02", "SEG-04", "SEG-05")  # pipeline corridors and the valve station
PRESSURE_INFO = {"SEG-01": "inlet terminal", "SEG-03": "pump station outlet", "SEG-06": "delivery terminal"}
NOISE_RANGE = (0.05, 0.12)  # bar, std of reported − actual pressure


# ---------------------------------------------------------------------------
# Plan


def _variables(scenario_type: str) -> tuple[str | None, ...]:
    return SENSOR_VARIABLES if scenario_type == "sensor_fault" else (None,)


def scenario_combinations(scenario_type: str) -> list[tuple[str, str, str | None]]:
    """Every (method, target, variable) of a scenario type, in the order its runs cycle through them.

    Each method lists its allowed targets in catalog order. Sensor faults pair each
    target with both variables: pressure and flow alternate along the targets, and
    the second pass swaps them. The methods are interleaved round-robin in catalog
    order, so every method recurs within a few runs. Exhausting one method before
    the next would, for example, never reach the sensor-fault "drift" method in the
    24 sensor-fault runs of the default plan (36 combinations).
    `variable` is None for every type except sensor_fault.
    """
    spec = _CATALOG[scenario_type]
    variables = _variables(scenario_type)
    lanes = [
        [(m["id"], target, variables[(i + p) % len(variables)])
         for p in range(len(variables)) for i, target in enumerate(m["allowed_targets"])]
        for m in spec["methods"]
    ]
    return [combo for group in zip_longest(*lanes) for combo in group if combo is not None]


def _scenario_parameters(rng: np.random.Generator) -> dict:
    """Random size and timing for one scenario run (four draws per run, always in this order)."""
    magnitude = round(float(rng.uniform(0.3, 1.0)), 2)
    onset_min = 4 + 0.5 * int(rng.integers(0, 13))  # 4.0, 4.5, …, 10.0
    active_min = 4 + 0.5 * int(rng.integers(0, 9))  # 4.0, 4.5, …, 8.0
    recovery = bool(rng.random() < 0.8)
    # validate_config needs the event and its recovery to end at least 1 min before the run does.
    room = DURATION_MIN - 1 - onset_min - RAMP_MIN - (RECOVERY_MIN if recovery else 0)
    return {"magnitude": magnitude, "onset_min": onset_min, "active_min": min(active_min, room), "recovery": recovery}


def _config(raw: dict, seed: int) -> ScenarioConfig:
    return validate_config(raw | {"ramp_min": RAMP_MIN, "duration_min": DURATION_MIN,
                                  "playback_speed": PLAYBACK_SPEED, "seed": seed})


def dataset_plan(seed=2026, n_train_normal=60, n_val_normal=20, n_val_scenario=30, n_test_normal=20,
                 n_test_scenario=90) -> list[tuple[str, str, ScenarioConfig]]:
    """(run_id, split, config) for every run, in run-id order.

    Train runs come first, then validation, then test; within a split, normal runs
    come before scenario runs. Train holds only normal runs. Scenario runs cycle
    through the five non-normal types in turn (index % 5), and each type cycles
    through `scenario_combinations` with one counter that continues from validation
    into test. Run seeds are unique and, like the scenario parameters, are drawn
    from `numpy.random.default_rng(seed)`.
    """
    layout = (("train", n_train_normal, 0), ("validation", n_val_normal, n_val_scenario),
              ("test", n_test_normal, n_test_scenario))
    if any(not isinstance(n, numbers.Integral) or n < 0 for _, *counts in layout for n in counts):
        raise ValueError("run counts must be non-negative integers")
    rng = np.random.default_rng(seed)
    total = sum(n_normal + n_scenario for _, n_normal, n_scenario in layout)
    seeds = iter(rng.choice(SEED_SPACE, size=total, replace=False).tolist())
    cycles = {t: scenario_combinations(t) for t in FAULT_TYPES}
    counters = dict.fromkeys(FAULT_TYPES, 0)

    plan: list[tuple[str, ScenarioConfig]] = []
    for split, n_normal, n_scenario in layout:
        for _ in range(n_normal):
            plan.append((split, _config({"scenario_type": "normal"}, next(seeds))))
        for i in range(n_scenario):
            scenario_type = FAULT_TYPES[i % len(FAULT_TYPES)]
            combos = cycles[scenario_type]
            method, target, variable = combos[counters[scenario_type] % len(combos)]
            counters[scenario_type] += 1
            raw = {"scenario_type": scenario_type, "method": method, "target_segment": target,
                   **_scenario_parameters(rng)}
            if variable is not None:
                raw["variable"] = variable
            plan.append((split, _config(raw, next(seeds))))
    return [(f"DS-{i:04d}", split, cfg) for i, (split, cfg) in enumerate(plan, start=1)]


_PLAN_DEFAULTS = {name: p.default for name, p in inspect.signature(dataset_plan).parameters.items()}


# ---------------------------------------------------------------------------
# Rows


def _iso(start: datetime, tick: int | None) -> str | None:
    return None if tick is None else (start + timedelta(seconds=TICK_SECONDS * tick)).isoformat()


def _run_row(run_id: str, split: str, cfg: ScenarioConfig, start: datetime) -> dict:
    scenario = cfg.scenario_type != "normal"
    return {
        "run_id": run_id, "split": split, "scenario_type": cfg.scenario_type,
        "method": cfg.method, "target_segment": cfg.target_segment,
        "variable": cfg.variable if cfg.scenario_type == "sensor_fault" else None,
        "magnitude": cfg.magnitude if scenario else None,
        "onset_min": cfg.onset_min if scenario else None,
        "ramp_min": cfg.ramp_min if scenario else None,
        "active_min": cfg.active_min if scenario else None,
        "recovery": cfg.recovery if scenario else None,
        "duration_min": cfg.duration_min, "seed": cfg.seed, "start_time": start.isoformat(),
    }


def _truth_row(run_id: str, data: RunData, start: datetime) -> dict:
    s = data.summary
    return {
        "run_id": run_id, "scenario_type": s.scenario_type, "method": s.method, "target_segment": s.target_segment,
        "event_start": _iso(start, s.event_start_tick), "event_peak": _iso(start, s.event_peak_tick),
        "event_end": _iso(start, s.event_end_tick),
        "event_start_tick": s.event_start_tick, "event_peak_tick": s.event_peak_tick,
        "event_end_tick": s.event_end_tick,
        "expected_root_cause": s.expected_root_cause, "manipulated_signal_or_asset": s.manipulated_signal_or_asset,
        "ground_truth_notes": s.notes,
    }


def _event_rows(run_id: str, data: RunData, start: datetime) -> list[dict]:
    return [
        {"timestamp": _iso(start, e.tick), "run_id": run_id, "tick": e.tick, "segment_id": e.segment,
         "event_source": e.source, "category": e.category, "event_type": e.event_type,
         "authorized": e.authorized, "severity": e.severity, "details": e.details, "observable": e.observable}
        for e in data.events
    ]


def _telemetry_frame(run_id: str, data: RunData, start: datetime) -> pd.DataFrame:
    """One row per tick and segment, tick-major, so a column reshapes straight to (T, 6)."""
    n_ticks, n_seg = data.n_ticks, len(data.segment_codes)
    ticks = np.repeat(np.arange(n_ticks), n_seg)
    stamps = np.datetime64(start, "s") + ticks * np.timedelta64(TICK_SECONDS, "s")
    cols = {
        "timestamp": np.datetime_as_string(stamps, unit="s"),
        "run_id": run_id,
        "segment_id": np.tile(np.array(data.segment_codes, dtype=object), n_ticks),
        "tick": ticks,
        "scenario_phase": np.repeat(data.phase, n_seg),
        "valve_state": data.valve_state.ravel(),
        "equipment_state": data.equipment_state.ravel(),
        "is_target": np.tile(data.is_target, n_ticks),
        "process_affected": data.process_affected.ravel(),
        "reporting_compromised": data.reporting_compromised.ravel(),
    }
    for var, column in (("pressure", "pressure_bar"), ("flow", "flow_m3h"), ("temperature", "temperature_c"),
                        ("valve_open", "valve_open_pct"), ("pump_speed", "pump_speed_pct")):
        cols[f"actual_{column}"] = np.round(data.actual[var], 3).ravel()
        cols[f"reported_{column}"] = data.reported[var].ravel()  # already rounded by the engine
    return pd.DataFrame(cols, columns=TELEMETRY_COLUMNS)


def _write_csv(frame: pd.DataFrame, path: Path) -> None:
    # No gzip timestamp and "\n" line ends on every OS, so regenerating with the same seed gives identical bytes.
    compression = {"method": "gzip", "mtime": 0} if path.suffix == ".gz" else None
    frame.to_csv(path, index=False, lineterminator="\n", encoding="utf-8", compression=compression)


# ---------------------------------------------------------------------------
# Calibration and data card


def _check(name: str, passed: bool, value) -> dict:
    return {"check": name, "passed": bool(passed), "value": value}


def _in(value: float, bounds: tuple[float, float]) -> bool:
    return bool(bounds[0] <= value <= bounds[1])  # False for NaN


def _calibration(tel: pd.DataFrame, normal: pd.DataFrame) -> tuple[list[dict], dict[str, float]]:
    """The four workbook calibration checks, plus the informational pressure means."""
    # 1. Cadence: within every run and segment, consecutive ticks are exactly one tick (5 s) apart.
    frame = pd.DataFrame({
        "run": tel["run_id"], "seg": tel["segment_id"], "tick": tel["tick"],
        "ts": pd.to_datetime(tel["timestamp"], format="%Y-%m-%dT%H:%M:%S"),
    }).sort_values(["run", "seg", "tick"])
    grouped = frame.groupby(["run", "seg"], sort=False)
    gaps = grouped["ts"].diff().dropna().dt.total_seconds()
    steps = grouped["tick"].diff().dropna()
    cadence_ok = len(gaps) > 0 and bool((gaps == TICK_SECONDS).all() and (steps == 1).all())
    cadence = {"intervals": len(gaps),
               "min_s": float(gaps.min()) if len(gaps) else None,
               "max_s": float(gaps.max()) if len(gaps) else None}

    # 2. Flow: median over normal runs of each run's mean reported flow.
    run_flow = normal.groupby("run_id")["reported_flow_m3h"].mean()
    flow = {"median": float(run_flow.median()) if len(run_flow) else float("nan"),
            "run_min": float(run_flow.min()) if len(run_flow) else float("nan"),
            "run_max": float(run_flow.max()) if len(run_flow) else float("nan"),
            "runs": len(run_flow)}

    # 3. Pressure: mean reported pressure per segment on normal runs.
    seg_pressure = normal.groupby("segment_id")["reported_pressure_bar"].mean()
    pressure = {s: float(seg_pressure.get(s, float("nan"))) for s in PRESSURE_CHECKED}
    info = {s: float(seg_pressure.get(s, float("nan"))) for s in PRESSURE_INFO}

    # 4. Noise: spread of the measurement error on pressure.
    residual = normal["reported_pressure_bar"] - normal["actual_pressure_bar"]
    noise = {"std": float(residual.std()) if len(residual) > 1 else float("nan"), "readings": len(residual)}

    checks = [
        _check("cadence", cadence_ok, cadence),
        _check("flow", _in(flow["median"], FLOW_RANGE), flow),
        _check("pressure", all(_in(v, PRESSURE_RANGE) for v in pressure.values()), pressure),
        _check("noise", _in(noise["std"], NOISE_RANGE), noise),
    ]
    return checks, info


def _display_path(path: Path) -> str:
    """The output directory relative to backend/ when it lies inside it (e.g. ml/data)."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(BACKEND_DIR).as_posix()
    except ValueError:
        return resolved.as_posix()


def _command(out_dir: Path, settings: dict) -> str:
    """The command that regenerates this dataset: the CLI when the counts match a preset, else the API call."""
    out = _display_path(out_dir)
    cli = f"python -m ml.generate_dataset --out {shlex.quote(out)} --seed {settings['seed']}"
    counts = {k: v for k, v in settings.items() if k != "seed"}
    if counts == {k: v for k, v in _PLAN_DEFAULTS.items() if k != "seed"}:
        return cli
    if counts == SMALL_PLAN:
        return cli + " --small"
    args = ", ".join(f"{k}={v!r}" for k, v in settings.items())
    return f'python -c "from ml.generate_dataset import generate_dataset; generate_dataset({out!r}, {args})"'


def _size(n_bytes: int) -> str:
    return f"{n_bytes / 1e6:.2f} MB" if n_bytes >= 1e6 else f"{n_bytes / 1e3:.1f} kB"


def _targets(codes) -> str:
    codes = sorted(set(codes))
    if len(codes) == len(SEGMENTS):
        return "all six"
    return ", ".join(codes) if codes else "–"


def _data_card(command: str, settings: dict, runs: pd.DataFrame, tel: pd.DataFrame, normal: pd.DataFrame,
               events: pd.DataFrame, files: dict[str, int], checks: list[dict], info: dict[str, float]) -> str:
    seed = settings["seed"]
    split_n = {s: int((runs["split"] == s).sum()) for s in SPLITS}
    n_ticks = DURATION_MIN * 60 // TICK_SECONDS
    n_normal = int((runs["scenario_type"] == "normal").sum())
    out = [
        "# Sensify mock dataset: data card",
        "",
        "Synthetic telemetry, control/security events and ground-truth labels for the six-segment Dhahran → Jubail "
        "pipeline (SEG-01 … SEG-06). Every run comes from the simulator the live app uses "
        "(`app.sim.engine.simulate_run`), so training data and demo runs share one physics model. The values are mock "
        "simulation values, not real measurements. Generator: `backend/ml/generate_dataset.py`.",
        "",
        "## Generation",
        "",
        "Run from `backend/`:",
        "",
        "```",
        command,
        "```",
        "",
        "| Setting | Value |",
        "|---|---|",
        f"| Base seed | {seed} |",
        f"| Runs | {len(runs)}: train {split_n['train']}, validation {split_n['validation']}, test {split_n['test']} |",
        f"| Run length | {DURATION_MIN} simulated minutes = {n_ticks} ticks of {TICK_SECONDS} s (playback speed "
        f"{PLAYBACK_SPEED}, which does not affect the data) |",
        f"| Start times | Run k (k = 0, 1, … in run-id order) starts at {START_TIME.isoformat()} + k h; tick t is "
        f"stamped start + {TICK_SECONDS} s × t |",
        f"| Run seeds | Unique, drawn without replacement from 0–{SEED_SPACE - 1:,} by "
        f"`numpy.random.default_rng({seed})`, which then draws the scenario parameters |",
        "| Scenario parameters | magnitude ~ U(0.3, 1.0), 2 dp; onset ~ U{4, 4.5, …, 10} min; ramp 1 min; "
        "active ~ U{4, 4.5, …, 8} min, shortened when needed so the event and its recovery end at least 1 min "
        "before the run does; recovery on with probability 0.8 |",
        "| Scenario mix | Each split cycles through the five non-normal types in turn. Within a type, runs cycle "
        "through every (method, allowed target) combination of the scenario catalog, and for sensor faults also "
        "the variable (pressure, flow). Methods are interleaved so that each recurs within a few runs. One counter "
        "per type continues from validation into test, so the two splits start at different combinations. |",
        f"| Software | numpy {np.__version__}, pandas {pd.__version__} |",
        "",
        "Running the command again with the same seed and software regenerates identical data files.",
        "",
        "## Files",
        "",
        "| File | Rows | Size | Contents |",
        "|---|---:|---:|---|",
        f"| `runs.csv` | {len(runs):,} | {_size(files['runs.csv'])} | One row per run: split, scenario parameters, "
        "seed, start time. Scenario parameters are blank for normal runs; `variable` applies to sensor faults "
        "only. |",
        f"| `telemetry.csv.gz` | {len(tel):,} | {_size(files['telemetry.csv.gz'])} | One row per run × tick × "
        "segment, ordered by run, tick, segment: actual and reported pressure (bar), flow (m³/h) and temperature "
        "(°C); valve opening and pump speed in % (blank where the segment has no valve or pump); reported valve "
        "and equipment state; ground-truth labels. |",
        f"| `events.csv` | {len(events):,} | {_size(files['events.csv'])} | Control, security, device and process "
        "events on the run's timebase. `observable = False` marks ground-truth-only events. |",
        f"| `ground_truth.csv` | {len(runs):,} | {_size(files['ground_truth.csv'])} | One row per run: scenario, "
        "target, event start/peak/end as timestamps and ticks (blank for normal runs), expected root cause, "
        "manipulated signal or asset, notes. |",
        "",
        "Column notes:",
        "",
        "- Ground truth, for labelling and evaluation only (the analysis must never read it): the `actual_*` "
        "telemetry columns, `scenario_phase`, `is_target`, `process_affected`, `reporting_compromised`, events with "
        "`observable = False`, `ground_truth.csv` and the scenario columns of `runs.csv`. The analysis sees the "
        "`reported_*` columns, `valve_state`, `equipment_state` and observable events.",
        "- `actual_*` is the underlying process, rounded to 3 decimals. `reported_*` is what the instruments "
        "report (0.01 bar, 0.1 m³/h, 0.01 °C, 0.1 %).",
        "- `scenario_phase` is one of baseline, onset, active, peak (active ticks with at least 90 % of the run's "
        "maximum effect), recovery, recovered.",
        "- `is_target` marks the scenario's target segment. `process_affected` means actual pressure or flow "
        "differs from the same run without the scenario by more than 4σ. `reporting_compromised` means reported "
        "differs from actual by more than 4σ, or a replay or hold is active at the segment.",
        "- `n/a` (events `authorized`) and `None` (`manipulated_signal_or_asset` of normal runs) are values, not "
        "missing data. pandas reads them as NaN by default; pass `keep_default_na=False, na_values=[\"\"]` to "
        "keep them. Blank cells are missing values.",
        "",
        "## Splits",
        "",
        "Train, validation and test are split by run: every run (all its ticks, segments and events) belongs to "
        "exactly one split, so nothing leaks between them. Train holds only normal runs, from which the detector "
        "learns normal behaviour. Validation is for tuning, and test is for the reported metrics.",
        "",
        "| Scenario type | Train | Validation | Test | Total |",
        "|---|---:|---:|---:|---:|",
    ]
    table = pd.crosstab(runs["scenario_type"], runs["split"])
    for scenario_type in SCENARIO_TYPES:
        row = [int(table.at[scenario_type, s]) if scenario_type in table.index and s in table.columns else 0
               for s in SPLITS]
        out.append(f"| {scenario_type} | " + " | ".join(map(str, row)) + f" | {sum(row)} |")
    out.append("| **Total** | " + " | ".join(f"**{split_n[s]}**" for s in SPLITS) + f" | **{len(runs)}** |")

    out += [
        "",
        "Scenario coverage (validation and test):",
        "",
        "| Scenario type | Method | Variable | Validation | Test | Targets in validation | Targets in test |",
        "|---|---|---|---:|---:|---|---|",
    ]
    for scenario_type in FAULT_TYPES:
        for method in (m["id"] for m in _CATALOG[scenario_type]["methods"]):
            for variable in _variables(scenario_type):
                rows = runs[(runs["scenario_type"] == scenario_type) & (runs["method"] == method)]
                if variable is not None:
                    rows = rows[rows["variable"] == variable]
                val, test = rows[rows["split"] == "validation"], rows[rows["split"] == "test"]
                out.append(f"| {scenario_type} | {method} | {variable or '–'} | {len(val)} | {len(test)} | "
                           f"{_targets(val['target_segment'])} | {_targets(test['target_segment'])} |")

    out += [
        "",
        "## Value ranges",
        "",
        f"Reported values on the {n_normal} normal runs (all splits), min / mean / max:",
        "",
        "| Segment | Pressure (bar) | Flow (m³/h) | Temperature (°C) |",
        "|---|---|---|---|",
    ]
    stats = normal.groupby("segment_id")[["reported_pressure_bar", "reported_flow_m3h", "reported_temperature_c"]]
    stats = stats.agg(["min", "mean", "max"])
    for seg in SEGMENTS:
        if seg.code not in stats.index:
            continue
        cells = []
        for column, digits in (("reported_pressure_bar", 2), ("reported_flow_m3h", 1), ("reported_temperature_c", 2)):
            lo, mean, hi = (stats.at[seg.code, (column, agg)] for agg in ("min", "mean", "max"))
            cells.append(f"{lo:.{digits}f} / {mean:.{digits}f} / {hi:.{digits}f}")
        out.append(f"| {seg.code} {seg.name} | " + " | ".join(cells) + " |")

    out += [
        "",
        "## Events",
        "",
        "| Category | Observable | Ground truth only | Total |",
        "|---|---:|---:|---:|",
    ]
    observable = events["observable"].astype(bool) if len(events) else pd.Series(dtype=bool)
    categories = list(EVENT_CATEGORIES) + sorted(set(events["category"]) - set(EVENT_CATEGORIES))
    for category in categories:
        in_cat = events["category"] == category
        seen_n, hidden_n = int((in_cat & observable).sum()), int((in_cat & ~observable).sum())
        out.append(f"| {category} | {seen_n} | {hidden_n} | {seen_n + hidden_n} |")
    out.append(f"| **Total** | **{int(observable.sum())}** | **{int((~observable).sum())}** | **{len(events)}** |")
    out += [
        "",
        "Observable events are the evidence a real monitoring system would have: operator and unauthorized "
        "commands, equipment state changes, security-monitor alerts, reporting-configuration changes and device "
        "diagnostics. Ground-truth-only events (`observable = False`, such as \"Leak begins\") record what actually "
        "happened and are for labelling and evaluation only.",
        "",
    ]
    out += _calibration_section(checks, info)
    out += [
        "",
        "## Not in this dataset",
        "",
        "The workbook's analysis columns (anomaly_score, telemetry_trust, incident_flag) are outputs of the system, "
        "not part of the generated data. Sensify's analysis computes them from the reported telemetry and "
        "observable events.",
        "",
    ]
    return "\n".join(out)


def _calibration_section(checks: list[dict], info: dict[str, float]) -> list[str]:
    by_name = {c["check"]: c for c in checks}
    cadence, flow = by_name["cadence"]["value"], by_name["flow"]["value"]
    pressure, noise = by_name["pressure"]["value"], by_name["noise"]["value"]
    if cadence["intervals"]:
        cadence_text = f"{cadence['intervals']:,} intervals; min {cadence['min_s']:g} s, max {cadence['max_s']:g} s"
    else:
        cadence_text = "no intervals"
    rows = [
        ("Cadence", f"Consecutive ticks of every run and segment are exactly {TICK_SECONDS} s apart (workbook: "
                    f"{TICK_SECONDS} s sampling)", cadence_text),
        ("Flow", f"Median of the per-run mean reported flow on normal runs is within {FLOW_RANGE[0]:g}–"
                 f"{FLOW_RANGE[1]:g} m³/h (workbook baseline flows 800–853 m³/h)",
         f"{flow['median']:.1f} m³/h (per-run means {flow['run_min']:.1f}–{flow['run_max']:.1f} over "
         f"{flow['runs']} runs)"),
        ("Pressure", f"Mean reported pressure on normal runs at the pipeline and valve segments "
                     f"{', '.join(PRESSURE_CHECKED)} each lies within {PRESSURE_RANGE[0]:g}–{PRESSURE_RANGE[1]:g} "
                     "bar (workbook baseline 69.8–73.2 bar)",
         ", ".join(f"{seg} {value:.2f} bar" for seg, value in pressure.items())),
        ("Noise", f"Standard deviation of reported − actual pressure on normal runs is within {NOISE_RANGE[0]:g}–"
                  f"{NOISE_RANGE[1]:g} bar", f"{noise['std']:.3f} bar over {noise['readings']:,} readings"),
    ]
    lines = [
        "## Calibration against the mock-data workbook",
        "",
        "| # | Check | Criterion | Measured | Result |",
        "|---|---|---|---|---|",
    ]
    for i, ((name, criterion, measured), check) in enumerate(zip(rows, checks), start=1):
        lines.append(f"| {i} | {name} | {criterion} | {measured} | {'PASS' if check['passed'] else 'FAIL'} |")
    passed = sum(c["passed"] for c in checks)
    info_text = ", ".join(f"{seg} ({label}) {info[seg]:.2f} bar" for seg, label in PRESSURE_INFO.items())
    lines += [
        "",
        f"For information only, the mean reported pressure on normal runs at the line's control points: {info_text}. "
        "The inlet header and the pump discharge run above the corridor baseline and the delivery terminal runs "
        "below it, by design, so they are not compared with the workbook band.",
        "",
        f"{passed} of {len(checks)} checks pass.",
    ]
    return lines


# ---------------------------------------------------------------------------
# Entry points


def generate_dataset(out_dir: Path, **plan_kwargs) -> dict:
    """Simulate every planned run and write the dataset into out_dir (created if needed). Returns a summary."""
    started = time.perf_counter()
    out_dir = Path(out_dir)
    settings = _PLAN_DEFAULTS | plan_kwargs
    plan = dataset_plan(**settings)

    run_rows, truth_rows, event_rows, frames = [], [], [], []
    for index, (run_id, split, cfg) in enumerate(plan):
        start = START_TIME + index * RUN_SPACING
        data = simulate_run(cfg)
        run_rows.append(_run_row(run_id, split, cfg, start))
        truth_rows.append(_truth_row(run_id, data, start))
        event_rows.extend(_event_rows(run_id, data, start))
        frames.append(_telemetry_frame(run_id, data, start))

    runs = pd.DataFrame(run_rows, columns=RUNS_COLUMNS)
    tel = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=TELEMETRY_COLUMNS)
    events = pd.DataFrame(event_rows, columns=EVENTS_COLUMNS[1:])
    events.insert(0, "event_id", [f"EV-{i:05d}" for i in range(1, len(events) + 1)])
    truth = pd.DataFrame(truth_rows, columns=GROUND_TRUTH_COLUMNS)
    for column in ("event_start_tick", "event_peak_tick", "event_end_tick"):
        truth[column] = truth[column].astype("Int64")

    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in zip(DATA_FILES, (runs, tel, events, truth)):
        _write_csv(frame, out_dir / name)
    files = {name: (out_dir / name).stat().st_size for name in DATA_FILES}

    normal = tel[tel["run_id"].isin(runs.loc[runs["scenario_type"] == "normal", "run_id"])]
    checks, info = _calibration(tel, normal)
    card = _data_card(_command(out_dir, settings), settings, runs, tel, normal, events, files, checks, info)
    (out_dir / "DATA_CARD.md").write_text(card, encoding="utf-8", newline="\n")
    files["DATA_CARD.md"] = (out_dir / "DATA_CARD.md").stat().st_size

    return {
        "out_dir": str(out_dir),
        "settings": settings,
        "runs": len(runs),
        "rows": len(tel),
        "events": len(events),
        "splits": {s: int((runs["split"] == s).sum()) for s in SPLITS},
        "types": {s: {t: int(((runs["split"] == s) & (runs["scenario_type"] == t)).sum()) for t in SCENARIO_TYPES}
                  for s in SPLITS},
        "files": files,
        "calibration": checks,
        "seconds": round(time.perf_counter() - started, 2),
    }


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(prog="python -m ml.generate_dataset",
                                     description="Generate the seeded Sensify mock dataset.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (default: backend/ml/data)")
    parser.add_argument("--seed", type=int, default=_PLAN_DEFAULTS["seed"], help="base seed (default: 2026)")
    parser.add_argument("--small", action="store_true",
                        help="small smoke-test dataset: 4 train, 2+5 validation and 2+10 test runs")
    args = parser.parse_args(argv)
    summary = generate_dataset(args.out, seed=args.seed, **(SMALL_PLAN if args.small else {}))
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
