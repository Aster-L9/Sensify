"""
Load the generated dataset (ml/data) for training and evaluation.

Each run's ReportedRun is built from the reported_* columns and observable events
only, so the model sees exactly what the live analysis sees. Labels are loaded
separately and used only to measure the model.
"""
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from app.analysis.frame import ObservableEvent, ReportedRun
from app.sim.topology import SEGMENT_CODES

N_SEG = len(SEGMENT_CODES)
REPORTED_COLUMNS = {
    "pressure": "reported_pressure_bar",
    "flow": "reported_flow_m3h",
    "temperature": "reported_temperature_c",
    "valve_open": "reported_valve_open_pct",
    "pump_speed": "reported_pump_speed_pct",
}


@dataclass
class RunLabels:
    phase: np.ndarray  # (T,)
    is_target: np.ndarray  # (6,) bool
    process_affected: np.ndarray  # (T, 6) bool
    reporting_compromised: np.ndarray  # (T, 6) bool
    event_start_tick: int | None
    event_peak_tick: int | None
    event_end_tick: int | None


@dataclass
class DatasetRun:
    run_id: str
    split: str
    scenario_type: str
    method: str | None
    target_segment: str | None
    magnitude: float
    reported: ReportedRun | None
    labels: RunLabels


def _optional_int(value) -> int | None:
    return None if pd.isna(value) else int(value)


def _optional_str(value) -> str | None:
    return None if pd.isna(value) else str(value)


def load_dataset(path: Path) -> list[DatasetRun]:
    path = Path(path)
    # Only empty cells are missing: literal values such as "n/a" (authorization) and "None" must survive.
    text_csv = {"keep_default_na": False, "na_values": [""]}
    runs = pd.read_csv(path / "runs.csv", **text_csv)
    tel = pd.read_csv(path / "telemetry.csv.gz")
    events = pd.read_csv(path / "events.csv", **text_csv)
    truth = pd.read_csv(path / "ground_truth.csv", **text_csv).set_index("run_id")

    seg_order = {code: i for i, code in enumerate(SEGMENT_CODES)}
    tel["seg_idx"] = tel["segment_id"].map(seg_order)
    tel = tel.sort_values(["run_id", "tick", "seg_idx"])
    observable = events[events["observable"].astype(str).str.lower() == "true"]
    events_by_run = {rid: df for rid, df in observable.groupby("run_id")}

    out = []
    for rid, df in tel.groupby("run_id", sort=False):
        n_ticks = df["tick"].max() + 1

        def grid(column: str, dtype=float) -> np.ndarray:
            return df[column].to_numpy(dtype=dtype).reshape(n_ticks, N_SEG)

        run_events = [
            ObservableEvent(int(e.tick), _optional_str(e.segment_id), e.event_source, e.category, e.event_type,
                            e.authorized, e.severity)
            for e in events_by_run.get(rid, pd.DataFrame()).itertuples()
        ]
        reported = ReportedRun(*(grid(col) for col in REPORTED_COLUMNS.values()), events=run_events)
        meta = runs.loc[runs["run_id"] == rid].iloc[0]
        gt = truth.loc[rid]
        labels = RunLabels(
            phase=df["scenario_phase"].to_numpy(dtype=object).reshape(n_ticks, N_SEG)[:, 0],
            is_target=grid("is_target", bool)[0],
            process_affected=grid("process_affected", bool),
            reporting_compromised=grid("reporting_compromised", bool),
            event_start_tick=_optional_int(gt["event_start_tick"]),
            event_peak_tick=_optional_int(gt["event_peak_tick"]),
            event_end_tick=_optional_int(gt["event_end_tick"]),
        )
        out.append(DatasetRun(
            run_id=rid, split=meta["split"], scenario_type=meta["scenario_type"],
            method=_optional_str(meta["method"]), target_segment=_optional_str(meta["target_segment"]),
            magnitude=float(meta["magnitude"]), reported=reported, labels=labels,
        ))
    return out


def split(runs: list[DatasetRun], name: str) -> list[DatasetRun]:
    return [r for r in runs if r.split == name]
