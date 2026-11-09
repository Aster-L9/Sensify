"""
Held-out scenario set (design 6.2), built independently of the analysis and investigation code.

Labels come only from scenario settings and from the observable events of each simulated run
(no analysis or model is run on the data). Output files match ml/data, with split "heldout",
plus labels.csv. Reproducible from a seed.

CLI (from backend/):  python -m ml.generate_heldout [--out ml/heldout] [--seed 4242]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.sim.engine import RunData, simulate_run
from app.sim.scenarios import CATALOG, RECOVERY_MIN, ScenarioConfig, validate_config
from app.sim.topology import SEGMENT_CODES
from ml.generate_dataset import (
    BACKEND_DIR, DATA_FILES, EVENTS_COLUMNS, GROUND_TRUTH_COLUMNS, RUN_SPACING, RUNS_COLUMNS, SEED_SPACE,
    START_TIME, _event_rows, _run_row, _telemetry_frame, _truth_row, _write_csv,
)

DEFAULT_OUT = BACKEND_DIR / "ml" / "heldout"
DEFAULT_SEED = 4242
PER_TYPE = 12
TYPES = ("normal", "physical_anomaly", "sensor_fault", "telemetry_manipulation", "unauthorized_control",
         "concealed_physical_incident")
LABEL_COLUMNS = ["run_id", "ambiguous", "expected_category", "acceptable_outcomes", "expected_segment",
                 "expected_ot_layers", "ambiguity_note"]
CATEGORY = {
    "normal": "normal_behaviour", "physical_anomaly": "physical_anomaly", "sensor_fault": "sensor_fault",
    "telemetry_manipulation": "cyber_manipulation", "unauthorized_control": "cyber_manipulation",
    "concealed_physical_incident": "reporting_inconsistency",
}
LAYERS = {
    "normal": "", "physical_anomaly": "physical_process", "sensor_fault": "field_device",
    "telemetry_manipulation": "reporting", "unauthorized_control": "control",
    "concealed_physical_incident": "physical_process|reporting",
}
ONSETS = (1, 2, 3, 4, 10, 12, 14, 16, 18)
_CAT = {t["id"]: t for t in CATALOG}

# Recipe slots per scenario type ("plain" = not ambiguous)
SLOTS = {
    "physical_anomaly": ["small_leak_edge"] * 4 + ["overlap"] + ["plain"] * 7,
    "sensor_fault": ["slow_drift"] * 4 + ["overlap"] + ["plain"] * 7,
    "telemetry_manipulation": ["bias_no_event"] * 4 + ["plain"] * 8,
    "unauthorized_control": ["no_security_event"] * 4 + ["overlap"] + ["plain"] * 7,
    "concealed_physical_incident": ["overlap"] + ["plain"] * 11,
}


def _timing(rng, index: int, slow: bool = False) -> dict:
    """Out-of-range timing: onset 1-4 or 10-18, ramp 2-5, active 9-15, duration 25-30, recovery off for odd index."""
    for _ in range(1000):
        onset = float(rng.choice(ONSETS))
        ramp = float(rng.integers(4, 6)) if slow else float(rng.integers(2, 6))
        active = float(rng.integers(9, 16))
        duration = float(rng.integers(25, 31))
        recovery = index % 2 == 0
        if onset + ramp + active + (RECOVERY_MIN if recovery else 0) <= duration - 1:
            return {"onset_min": onset, "ramp_min": ramp, "active_min": active, "duration_min": duration,
                    "recovery": recovery}
    raise RuntimeError("no timing fits")


def _pick(rng, options):
    return options[int(rng.integers(0, len(options)))]


def _raw(rng, scenario_type: str, index: int, recipe: str) -> dict:
    methods = {m["id"]: m["allowed_targets"] for m in _CAT[scenario_type]["methods"]}
    raw = {"scenario_type": scenario_type, "magnitude": round(float(rng.uniform(0.1, 0.3)), 2),
           **_timing(rng, index, slow=recipe == "slow_drift")}
    if scenario_type == "physical_anomaly":
        if recipe == "small_leak_edge":
            raw.update(method="leak", target_segment=_pick(rng, ["SEG-01", "SEG-06"]),
                       magnitude=round(float(rng.uniform(0.1, 0.2)), 2))
        else:
            raw.update(method=_pick(rng, ["leak", "blockage"]), target_segment=_pick(rng, list(SEGMENT_CODES)))
    elif scenario_type == "sensor_fault":
        raw.update(method="drift" if recipe == "slow_drift" else _pick(rng, ["erratic", "stuck"]),
                   target_segment=_pick(rng, list(SEGMENT_CODES)), variable=_pick(rng, ["pressure", "flow"]))
    elif scenario_type == "telemetry_manipulation":
        method = "bias" if recipe == "bias_no_event" else _pick(rng, ["replay", "bias"])
        raw.update(method=method, target_segment=_pick(rng, methods[method]))
    elif scenario_type == "unauthorized_control":
        method = _pick(rng, list(methods))
        raw.update(method=method, target_segment=methods[method][0])
    else:
        raw.update(method="leak", target_segment=_pick(rng, list(SEGMENT_CODES)))
    return raw


def _overlaps_operator(data: RunData, onset_tick: int) -> bool:
    """An authorized operator command within 1 minute (12 ticks) of the scenario onset."""
    return any(e.observable and e.category == "control" and e.authorized == "yes" and abs(e.tick - onset_tick) <= 12
               for e in data.events)


def _accept(scenario_type: str, recipe: str, cfg: ScenarioConfig, data: RunData) -> bool:
    seen = {e.event_type for e in data.events if e.observable}
    if scenario_type == "normal":
        return True
    if recipe == "overlap":
        return _overlaps_operator(data, cfg.onset_tick)
    if scenario_type == "telemetry_manipulation":
        has = "Reporting configuration change" in seen
        return not has if recipe == "bias_no_event" else has
    if scenario_type == "unauthorized_control":
        has = "Command from unregistered workstation" in seen
        return not has if recipe == "no_security_event" else has
    return True


def _label(run_id: str, scenario_type: str, recipe: str, cfg: ScenarioConfig) -> dict:
    cat = CATEGORY[scenario_type]
    outcomes, note = [cat], ""
    if recipe == "overlap":
        outcomes = [cat, "normal_behaviour", "uncertain"]
        note = "Scenario onset falls within 1 minute of a routine authorized operator command."
    elif recipe == "bias_no_event":
        outcomes = ["cyber_manipulation", "sensor_fault", "uncertain"]
        note = "False offset with no reporting configuration change event; resembles a sensor fault."
    elif recipe == "slow_drift":
        outcomes = ["sensor_fault", "uncertain"]
        note = "Slow, small sensor drift that grows gradually."
    elif recipe == "small_leak_edge":
        outcomes = ["physical_anomaly", "uncertain"]
        note = f"Small leak at {cfg.target_segment}, an end segment with few neighbours to corroborate."
    elif recipe == "no_security_event":
        outcomes = ["cyber_manipulation", "uncertain"]
        note = "Unauthorized control with no command-from-unregistered-workstation event."
    return {"run_id": run_id, "ambiguous": recipe != "plain", "expected_category": cat,
            "acceptable_outcomes": "|".join(outcomes), "expected_segment": cfg.target_segment or "",
            "expected_ot_layers": LAYERS[scenario_type], "ambiguity_note": note}


def heldout_plan(seed: int = DEFAULT_SEED) -> list[tuple[str, str, ScenarioConfig, RunData]]:
    """(run_id, recipe, config, simulated data) for the 72 runs; draws repeat until the recipe's events hold."""
    rng = np.random.default_rng(seed)
    used: set[int] = set()
    plan = []
    for scenario_type in TYPES:
        slots = ["plain"] * PER_TYPE if scenario_type == "normal" else SLOTS[scenario_type]
        for index, recipe in enumerate(slots):
            for _ in range(5000):
                if scenario_type == "normal":
                    raw = {"scenario_type": "normal", "duration_min": float(rng.integers(25, 31))}
                else:
                    raw = _raw(rng, scenario_type, index, recipe)
                run_seed = int(rng.integers(0, SEED_SPACE))
                if run_seed in used:
                    continue
                cfg = validate_config(raw | {"seed": run_seed, "playback_speed": 10})
                data = simulate_run(cfg)
                if _accept(scenario_type, recipe, cfg, data):
                    used.add(run_seed)
                    plan.append((f"HO-{len(plan) + 1:04d}", recipe, cfg, data))
                    break
            else:
                raise RuntimeError(f"no seed satisfies {scenario_type}/{recipe}")
    return plan


def generate_heldout(out_dir: Path = DEFAULT_OUT, seed: int = DEFAULT_SEED) -> dict:
    out_dir = Path(out_dir)
    plan = heldout_plan(seed)
    run_rows, truth_rows, event_rows, frames, labels = [], [], [], [], []
    for index, (run_id, recipe, cfg, data) in enumerate(plan):
        start = START_TIME + index * RUN_SPACING
        run_rows.append(_run_row(run_id, "heldout", cfg, start))
        truth_rows.append(_truth_row(run_id, data, start))
        event_rows.extend(_event_rows(run_id, data, start))
        frames.append(_telemetry_frame(run_id, data, start))
        labels.append(_label(run_id, cfg.scenario_type, recipe, cfg))
    runs = pd.DataFrame(run_rows, columns=RUNS_COLUMNS)
    tel = pd.concat(frames, ignore_index=True)
    events = pd.DataFrame(event_rows, columns=EVENTS_COLUMNS[1:])
    events.insert(0, "event_id", [f"EV-{i:05d}" for i in range(1, len(events) + 1)])
    truth = pd.DataFrame(truth_rows, columns=GROUND_TRUTH_COLUMNS)
    for column in ("event_start_tick", "event_peak_tick", "event_end_tick"):
        truth[column] = truth[column].astype("Int64")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in zip(DATA_FILES, (runs, tel, events, truth)):
        _write_csv(frame, out_dir / name)
    lab = pd.DataFrame(labels, columns=LABEL_COLUMNS)
    _write_csv(lab, out_dir / "labels.csv")
    amb = lab["ambiguous"].to_numpy()
    return {
        "out_dir": str(out_dir), "seed": seed, "runs": len(runs), "events": len(events),
        "types": {t: int((runs["scenario_type"] == t).sum()) for t in TYPES},
        "ambiguous": int(amb.sum()),
        "ambiguous_by_type": {t: int(amb[(runs["scenario_type"] == t).to_numpy()].sum()) for t in TYPES},
        "recovery_off": int((runs["recovery"] == False).sum()),  # noqa: E712
    }


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(prog="python -m ml.generate_heldout")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    summary = generate_heldout(args.out, args.seed)
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    main()
