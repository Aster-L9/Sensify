"""Seeded dataset generator and the generated dataset."""
import re

import numpy as np
import pandas as pd
import pytest

from app.sim.engine import simulate_run
from app.sim.scenarios import CATALOG, SCENARIO_TYPES, validate_config
from app.sim.topology import SEGMENT_CODES
from ml.generate_dataset import dataset_plan, generate_dataset, main, scenario_combinations

FAULT_TYPES = [t for t in SCENARIO_TYPES if t != "normal"]

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


def test_small_dataset_files_and_splits(tmp_path):
    summary = generate_dataset(tmp_path, seed=1, n_train_normal=2, n_val_normal=1, n_val_scenario=5, n_test_normal=1, n_test_scenario=5)
    runs = pd.read_csv(tmp_path / "runs.csv")
    assert summary["runs"] == len(runs) == 14
    assert set(runs.loc[runs.split == "train", "scenario_type"]) == {"normal"}
    tel = pd.read_csv(tmp_path / "telemetry.csv.gz")
    assert len(tel) == 14 * 240 * 6 and {"reported_pressure_bar", "actual_flow_m3h", "reporting_compromised"} <= set(tel.columns)
    assert (tmp_path / "events.csv").exists() and (tmp_path / "ground_truth.csv").exists() and (tmp_path / "DATA_CARD.md").exists()


def test_plan_is_deterministic_and_covers_types():
    a, b = dataset_plan(seed=3), dataset_plan(seed=3)
    assert [(r, s, c.seed) for r, s, c in a] == [(r, s, c.seed) for r, s, c in b]
    test_types = {c.scenario_type for _, s, c in a if s == "test"}
    assert test_types == set(SCENARIO_TYPES)


def test_plan_layout_and_parameters():
    plan = dataset_plan()
    assert [r for r, _, _ in plan] == [f"DS-{i:04d}" for i in range(1, 221)]
    assert [s for _, s, _ in plan] == ["train"] * 60 + ["validation"] * 50 + ["test"] * 110
    assert len({c.seed for _, _, c in plan}) == len(plan)
    assert all(c.playback_speed == 10 and c.duration_min == 20 and c.ramp_min == 1 for _, _, c in plan)
    scenarios = [c for _, _, c in plan if c.scenario_type != "normal"]
    assert len(scenarios) == 120
    for c in scenarios:
        assert 0.3 <= c.magnitude <= 1.0 and c.magnitude == round(c.magnitude, 2)
        assert 4 <= c.onset_min <= 10 and (2 * c.onset_min).is_integer()
        assert 4 <= c.active_min <= 8 and (2 * c.active_min).is_integer()
    assert 0.65 <= np.mean([c.recovery for c in scenarios]) <= 0.95
    assert dataset_plan(seed=2026) == plan and dataset_plan(seed=7) != plan


def test_combinations_enumerate_every_catalog_option():
    by_id = {t["id"]: t for t in CATALOG}
    for scenario_type in FAULT_TYPES:
        variables = ("pressure", "flow") if scenario_type == "sensor_fault" else (None,)
        expected = {(m["id"], target, v) for m in by_id[scenario_type]["methods"]
                    for target in m["allowed_targets"] for v in variables}
        combos = scenario_combinations(scenario_type)
        assert len(combos) == len(expected) and set(combos) == expected, scenario_type


def test_scenario_runs_cycle_types_and_combinations():
    plan = dataset_plan()
    for split, n in (("validation", 30), ("test", 90)):
        types = [c.scenario_type for _, s, c in plan if s == split and c.scenario_type != "normal"]
        assert types == [FAULT_TYPES[i % 5] for i in range(n)]
    for scenario_type in FAULT_TYPES:
        combos = scenario_combinations(scenario_type)
        used = [(c.method, c.target_segment, c.variable if scenario_type == "sensor_fault" else None)
                for _, _, c in plan if c.scenario_type == scenario_type]
        # one counter per type that continues from validation into test
        assert used == [combos[k % len(combos)] for k in range(len(used))], scenario_type
    # every method appears in both evaluation splits; test sensor faults reach every segment and both variables
    for scenario_type in FAULT_TYPES:
        methods = {m for m, _, _ in scenario_combinations(scenario_type)}
        for split in ("validation", "test"):
            assert {c.method for _, s, c in plan if s == split and c.scenario_type == scenario_type} == methods
    faults = [c for _, s, c in plan if s == "test" and c.scenario_type == "sensor_fault"]
    assert {c.target_segment for c in faults} == set(SEGMENT_CODES)
    assert {c.variable for c in faults} == {"pressure", "flow"}


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    out = tmp_path_factory.mktemp("small")
    main(["--out", str(out), "--seed", "4", "--small"])
    return out


def test_cli_small_files_have_the_specified_columns(small):
    runs = pd.read_csv(small / "runs.csv")
    assert list(runs.columns) == RUNS_COLUMNS
    assert runs.split.value_counts().to_dict() == {"train": 4, "validation": 7, "test": 12}
    assert list(pd.read_csv(small / "telemetry.csv.gz", nrows=1).columns) == TELEMETRY_COLUMNS
    assert list(pd.read_csv(small / "events.csv").columns) == EVENTS_COLUMNS
    assert list(pd.read_csv(small / "ground_truth.csv").columns) == GROUND_TRUTH_COLUMNS
    normal = runs[runs.scenario_type == "normal"]
    scenario_only = ["method", "target_segment", "variable", "magnitude", "onset_min", "ramp_min", "active_min", "recovery"]
    assert normal[scenario_only].isna().all().all() and normal.duration_min.eq(20).all()
    assert runs.loc[runs.scenario_type != "sensor_fault", "variable"].isna().all()


def test_telemetry_timebase_layout_and_rounding(small):
    runs = pd.read_csv(small / "runs.csv")
    tel = pd.read_csv(small / "telemetry.csv.gz")
    starts = pd.to_datetime(runs.start_time)
    assert starts.iloc[0] == pd.Timestamp("2026-09-01T00:00:00")
    assert (starts.diff().iloc[1:] == pd.Timedelta(hours=1)).all()
    expected = tel.run_id.map(dict(zip(runs.run_id, starts))) + pd.to_timedelta(5 * tel.tick, unit="s")
    assert (pd.to_datetime(tel.timestamp) == expected).all()
    assert list(tel.segment_id.iloc[:6]) == list(SEGMENT_CODES) and list(tel.tick.iloc[:7]) == [0] * 6 + [1]
    per = tel.groupby(["run_id", "segment_id"]).tick.agg(["min", "max", "count"])
    assert len(per) == len(runs) * 6
    assert (per["min"] == 0).all() and (per["max"] == 239).all() and (per["count"] == 240).all()
    for col, seg in (("reported_valve_open_pct", "SEG-05"), ("actual_valve_open_pct", "SEG-05"),
                     ("reported_pump_speed_pct", "SEG-03"), ("actual_pump_speed_pct", "SEG-03")):
        assert (tel[col].notna() == (tel.segment_id == seg)).all(), col
    for col in ("actual_pressure_bar", "actual_flow_m3h", "actual_temperature_c", "actual_valve_open_pct"):
        values = tel[col].dropna().to_numpy()
        assert np.allclose(values, np.round(values, 3), rtol=0, atol=1e-9), col


def test_rows_reproduce_the_simulator(small):
    runs = pd.read_csv(small / "runs.csv")
    tel = pd.read_csv(small / "telemetry.csv.gz", float_precision="round_trip")
    events = pd.read_csv(small / "events.csv")
    params = ["scenario_type", "method", "target_segment", "variable", "magnitude", "onset_min", "ramp_min",
              "active_min", "duration_min"]
    for scenario_type in ("normal", "sensor_fault", "telemetry_manipulation", "concealed_physical_incident"):
        row = runs[runs.scenario_type == scenario_type].iloc[0]
        raw = {k: row[k] for k in params if pd.notna(row[k])}
        if pd.notna(row.recovery):
            raw["recovery"] = str(row.recovery) == "True"
        data = simulate_run(validate_config(raw | {"seed": int(row.seed)}))
        run_tel = tel[tel.run_id == row.run_id]

        def grid(col):
            return run_tel[col].to_numpy().reshape(240, 6)

        assert np.array_equal(grid("reported_pressure_bar"), data.reported["pressure"])
        assert np.array_equal(grid("reported_flow_m3h"), data.reported["flow"])
        assert np.allclose(grid("actual_flow_m3h"), data.actual["flow"], rtol=0, atol=5e-4)
        assert np.array_equal(grid("reporting_compromised"), data.reporting_compromised)
        assert np.array_equal(grid("process_affected"), data.process_affected)
        assert list(run_tel.scenario_phase.iloc[::6]) == list(data.phase)
        assert list(events.loc[events.run_id == row.run_id, "event_type"]) == [e.event_type for e in data.events]


def test_ground_truth_and_events(small):
    runs = pd.read_csv(small / "runs.csv")
    gt = pd.read_csv(small / "ground_truth.csv")
    ev = pd.read_csv(small / "events.csv")
    assert list(gt.run_id) == list(runs.run_id) and list(gt.scenario_type) == list(runs.scenario_type)
    normal = gt.scenario_type == "normal"
    cols = ["event_start", "event_peak", "event_end", "event_start_tick", "event_peak_tick", "event_end_tick"]
    assert gt.loc[normal, cols].isna().all().all() and gt.loc[~normal, cols].notna().all().all()
    onset = gt.run_id.map(dict(zip(runs.run_id, runs.onset_min)))
    assert (gt.loc[~normal, "event_start_tick"] == onset[~normal] * 12).all()
    start = gt.run_id.map(dict(zip(runs.run_id, pd.to_datetime(runs.start_time))))
    stamped = start[~normal] + pd.to_timedelta(5 * gt.loc[~normal, "event_peak_tick"], unit="s")
    assert (pd.to_datetime(gt.loc[~normal, "event_peak"]) == stamped).all()
    assert list(ev.event_id) == [f"EV-{i:05d}" for i in range(1, len(ev) + 1)]
    assert ev.observable.dtype == bool and set(ev.run_id) <= set(runs.run_id)
    assert set(ev.loc[~ev.observable, "run_id"]) <= set(gt.loc[~normal, "run_id"])
    literal = pd.read_csv(small / "events.csv", keep_default_na=False, na_values=[""])
    assert "n/a" in set(literal.authorized) and set(literal.authorized) <= {"yes", "no", "unknown", "n/a"}


def test_data_card_has_command_and_four_calibration_checks(small):
    card = (small / "DATA_CARD.md").read_text(encoding="utf-8")
    assert "python -m ml.generate_dataset" in card and "--seed 4 --small" in card
    calibration = card.split("## Calibration", 1)[1].split("\n## ", 1)[0]
    assert len(re.findall(r"\b(?:PASS|FAIL)\b", calibration)) == 4
    for text in ("Cadence", "Flow", "Pressure", "Noise", "anomaly_score", "telemetry_trust", "incident_flag",
                 "split by run"):
        assert text in card, text


def test_generation_is_reproducible(tmp_path):
    kw = dict(seed=11, n_train_normal=1, n_val_normal=0, n_val_scenario=0, n_test_normal=1, n_test_scenario=5)
    a = generate_dataset(tmp_path / "a", **kw)
    generate_dataset(tmp_path / "b", **kw)
    assert a["rows"] == 7 * 240 * 6 and a["splits"] == {"train": 1, "validation": 0, "test": 6} and a["seconds"] >= 0
    for name in ("runs.csv", "telemetry.csv.gz", "events.csv", "ground_truth.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes(), name
