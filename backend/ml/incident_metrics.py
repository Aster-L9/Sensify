"""
Incident-level evaluation criteria (design §6.3).

Ground-truth labels are used here, and only here, to score what a system reported.
"""
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from ml.dataset import DatasetRun
from ml.metrics import GRACE_TICKS, _rate

EXPECTED_CATEGORY = {
    "normal": "normal_behaviour",
    "physical_anomaly": "physical_anomaly",
    "sensor_fault": "sensor_fault",
    "telemetry_manipulation": "cyber_manipulation",
    "unauthorized_control": "cyber_manipulation",
    "concealed_physical_incident": "reporting_inconsistency",
}
EXPECTED_LAYERS = {
    "normal": [],
    "physical_anomaly": ["physical_process"],
    "sensor_fault": ["field_device"],
    "telemetry_manipulation": ["reporting"],
    "unauthorized_control": ["control"],
    "concealed_physical_incident": ["physical_process", "reporting"],
}


@dataclass
class RunLabel:
    run_id: str
    scenario_type: str
    expected_category: str
    acceptable: list[str] = field(default_factory=list)
    expected_segment: str | None = None
    expected_layers: list[str] = field(default_factory=list)
    ambiguous: bool = False


def dev_labels(runs: list[DatasetRun]) -> dict[str, RunLabel]:
    out = {}
    for r in runs:
        cat = EXPECTED_CATEGORY[r.scenario_type]
        out[r.run_id] = RunLabel(r.run_id, r.scenario_type, cat, [cat], r.target_segment,
                                 list(EXPECTED_LAYERS[r.scenario_type]), False)
    return out


def _split_list(value) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [p.strip() for p in str(value).split("|") if p.strip()]


def heldout_labels(path: Path) -> dict[str, RunLabel]:
    """Read heldout/labels.csv (a directory is accepted too) and the scenario types from runs.csv beside it."""
    path = Path(path)
    if path.is_dir():
        path = path / "labels.csv"
    labels = pd.read_csv(path, keep_default_na=False, na_values=[""])
    types = {}
    runs_csv = path.parent / "runs.csv"
    if runs_csv.exists():
        runs = pd.read_csv(runs_csv, keep_default_na=False, na_values=[""])
        types = dict(zip(runs["run_id"], runs["scenario_type"]))
    out = {}
    for row in labels.itertuples(index=False):
        seg = None if pd.isna(row.expected_segment) else str(row.expected_segment)
        out[row.run_id] = RunLabel(
            row.run_id, types.get(row.run_id, ""), str(row.expected_category),
            _split_list(row.acceptable_outcomes), seg, _split_list(row.expected_ot_layers),
            str(row.ambiguous).strip().lower() == "true")
    return out


def _event_incident(run: DatasetRun, incidents: list[dict], can_classify: bool) -> dict | None:
    start = run.labels.event_start_tick
    end = run.labels.event_end_tick
    if start is None or end is None:
        return None
    end += GRACE_TICKS
    hits = [i for i in incidents if i["start_tick"] <= end and i["end_tick"] >= start]
    if not hits:
        return None

    def key(i):
        duration = i["end_tick"] - i["start_tick"]
        return (i.get("evidence_count", 0), duration) if can_classify else (duration,)
    return max(hits, key=key)


def incident_criteria(incidents_by_run: dict[str, list[dict]], runs: list[DatasetRun],
                      labels: dict[str, RunLabel], can_classify: bool) -> dict:
    scenario = [r for r in runs if r.scenario_type != "normal"]
    normal = [r for r in runs if r.scenario_type == "normal"]

    detected = decided = correct = 0
    seg_total = seg_ok = layer_total = layer_ok = 0
    amb_total = amb_ok = 0
    outside = 0
    confusion: dict[str, dict[str, int]] = {}

    def tally(expected: str, predicted: str):
        row = confusion.setdefault(expected, {})
        row[predicted] = row.get(predicted, 0) + 1

    for run in scenario:
        label = labels[run.run_id]
        incs = incidents_by_run.get(run.run_id, [])
        ev = _event_incident(run, incs, can_classify)
        outside += len(incs) - (1 if ev is not None else 0)
        if label.ambiguous:
            amb_total += 1
            if can_classify and ev is not None and ev["classification"] in label.acceptable:
                amb_ok += 1
        if ev is None:
            continue
        detected += 1
        if ev.get("segment_code") is not None and label.expected_segment:
            seg_total += 1
            seg_ok += int(ev["segment_code"] == label.expected_segment)
        if not can_classify:
            continue
        cls = ev["classification"]
        tally(label.expected_category, cls)
        if cls != "uncertain":
            decided += 1
            correct += int(cls == label.expected_category)
        if ev.get("ot_layers") and label.expected_layers:
            layer_total += 1
            layer_ok += int(set(ev["ot_layers"]) == set(label.expected_layers))

    normal_counts = [len(incidents_by_run.get(r.run_id, [])) for r in normal]
    unexplained = []
    for r in normal:
        incs = incidents_by_run.get(r.run_id, [])
        if can_classify:
            for i in incs:
                tally("normal_behaviour", i["classification"])
        unexplained.append(sum(1 for i in incs if not can_classify or i["classification"] != "normal_behaviour"))

    def mean(values):
        return (sum(values) / len(values)) if values else None

    return {
        "incident_detection": _rate(detected, len(scenario)),
        "classification_accuracy": _rate(correct, decided) if can_classify else None,
        "decision_coverage": _rate(decided, detected) if can_classify else None,
        "ambiguity_handled": _rate(amb_ok, amb_total) if can_classify and amb_total else None,
        "segment_localisation": _rate(seg_ok, seg_total),
        "ot_layer_accuracy": _rate(layer_ok, layer_total) if can_classify else None,
        "incidents_per_normal_run": mean(normal_counts),
        "unexplained_per_normal_run": mean(unexplained),
        "incidents_outside_event": outside,
        "confusion": confusion if can_classify else {},
    }
