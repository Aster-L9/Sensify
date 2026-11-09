"""
Evaluation harness (design §6.4): systems A (threshold alarms), B (ML only) and C (full hybrid)
scored on the development test split and the held-out set, always reported separately.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.analysis.model import DetectorModel
from app.analysis.pipeline import analyze_run
from app.investigation.config import DEFAULT_CONFIG, ENGINE_VERSION, EngineConfig
from app.investigation.engine import investigate
from app.investigation.grouping import group_flags
from app.sim.topology import SEGMENT_CODES
from ml.dataset import DatasetRun, load_dataset, split
from ml.incident_metrics import RunLabel, dev_labels, heldout_labels, incident_criteria
from ml.metrics import compare_targets, detection_metrics, trust_metrics

ML_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ML_DIR.parent
DATASET_TITLES = {"development": "Development (test split)", "heldout": "Held-out"}
TARGET_FILES = ("targets.json", "targets_investigation.json")


def load_all_targets() -> dict:
    targets = {}
    for name in TARGET_FILES:
        targets.update(json.loads((ML_DIR / name).read_text(encoding="utf-8")))
    return targets


def default_datasets(dev_dir: Path = ML_DIR / "data", heldout_dir: Path = ML_DIR / "heldout"
                     ) -> dict[str, tuple[list[DatasetRun], dict[str, RunLabel]]]:
    dev = split(load_dataset(dev_dir), "test")
    held = load_dataset(heldout_dir)
    return {"development": (dev, dev_labels(dev)),
            "heldout": (held, heldout_labels(Path(heldout_dir) / "labels.csv"))}


def _flag_incidents(flags: np.ndarray, pick: np.ndarray, cfg: EngineConfig) -> list[dict]:
    """Group flags into incidents (gap rule G); localise to the segment with the largest `pick` total in the span."""
    rows = []
    for s, e in group_flags(flags, cfg):
        totals = pick[s:e + 1].sum(axis=0)
        if totals.sum() <= 0:
            totals = flags[s:e + 1].sum(axis=0)
        rows.append({"start_tick": int(s), "end_tick": int(e), "detected_tick": int(s), "classification": None,
                     "confidence": None, "segment_code": SEGMENT_CODES[int(np.argmax(totals))], "ot_layers": [],
                     "evidence_count": 0, "severity": None})
    return rows


def evaluate(model: DetectorModel, datasets: dict[str, tuple[list[DatasetRun], dict[str, RunLabel]]],
             cfg: EngineConfig = DEFAULT_CONFIG) -> dict:
    targets = load_all_targets()
    result = {"engine_version": ENGINE_VERSION, "model_version": model.version,
              "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "datasets": {}, "targets": targets, "targets_check": {}, "per_run": []}
    for name, (runs, labels) in datasets.items():
        flags = {s: {} for s in "ABC"}
        incidents = {s: {} for s in "ABC"}
        trust = {}
        for run in runs:
            out = analyze_run(run.reported, model)
            rid = run.run_id
            flags["A"][rid] = out.baseline.any
            flags["B"][rid] = out.ml_flag
            flags["C"][rid] = out.state != "normal"
            incidents["A"][rid] = _flag_incidents(out.baseline.any, out.baseline.any.astype(float), cfg)
            incidents["B"][rid] = _flag_incidents(out.ml_flag, out.scores * out.ml_flag, cfg)
            incidents["C"][rid] = [i.summary_row() for i in investigate(run.reported, out, model.reference, cfg)]
            trust[rid] = out.trust.status
        trust_m = trust_metrics(trust, runs)
        systems = {}
        for s in "ABC":
            systems[s] = {"detection": detection_metrics(flags[s], runs),
                          "investigation": incident_criteria(incidents[s], runs, labels, can_classify=(s == "C"))}
        result["datasets"][name] = {"runs": len(runs), "trust": trust_m, "systems": systems}
        # A target may name the datasets it applies to (ambiguity is only measurable on held-out).
        applicable = {k: t for k, t in targets.items() if name in t.get("datasets", [name])}
        result["targets_check"][name] = compare_targets(
            {"ml": systems["C"]["detection"], "trust": trust_m, "C": systems["C"]["investigation"]}, applicable)
        for run in runs:
            lab = labels[run.run_id]
            result["per_run"].append({
                "dataset": name, "run_id": run.run_id, "scenario_type": run.scenario_type,
                "expected_category": lab.expected_category, "ambiguous": lab.ambiguous,
                "incidents": {s: incidents[s][run.run_id] for s in "ABC"}})
    return result


def _fmt(value) -> str:
    if value is None:
        return "not available"
    if isinstance(value, dict) and "rate" in value:
        if value["rate"] is None:
            return "not available"
        return f"{value['detected']}/{value['total']} ({value['rate'] * 100:.1f} %)"
    if isinstance(value, float):
        # Keep small rates visible: a 0.035 % false-alarm rate must not print as 0.000.
        return f"{value:.5f}" if 0 < abs(value) < 0.01 else f"{value:.3f}"
    return str(value)


def _rows(det: dict, inv: dict) -> list[tuple[str, object]]:
    return [
        ("Event detection", det["overall"]),
        ("Tick false-alarm rate on normal runs", det["false_alarm"]["tick_rate"]),
        ("False alert windows per normal run", det["false_alarm"]["windows_per_run"]),
        ("Window precision", det["window_precision"]),
        ("Median time to detect (s)", det["time_to_detect_s"]["median"]),
        ("Incident detection", inv["incident_detection"]),
        ("Classification accuracy", inv["classification_accuracy"]),
        ("Decision coverage", inv["decision_coverage"]),
        ("Ambiguity handled", inv["ambiguity_handled"]),
        ("Segment localisation", inv["segment_localisation"]),
        ("OT layer accuracy", inv["ot_layer_accuracy"]),
        ("Incidents per normal run", inv["incidents_per_normal_run"]),
        ("Unexplained incidents per normal run", inv["unexplained_per_normal_run"]),
        ("Incidents outside the event", inv["incidents_outside_event"]),
    ]


def render_report(result: dict) -> str:
    lines = [f"# Evaluation: engine {result['engine_version']}, model v{result['model_version']}", "",
             f"Created {result['created_at']}. Development and held-out results are never pooled.", ""]
    for name in ("development", "heldout"):
        d = result["datasets"].get(name)
        if d is None:
            continue
        lines += [f"## {DATASET_TITLES[name]} ({d['runs']} runs)", "",
                  "| Criterion | A. Threshold only | B. ML only | C. Full hybrid |", "|---|---|---|---|"]
        cols = [_rows(d["systems"][s]["detection"], d["systems"][s]["investigation"]) for s in "ABC"]
        for i, (label, _) in enumerate(cols[0]):
            lines.append(f"| {label} | " + " | ".join(_fmt(c[i][1]) for c in cols) + " |")
        lines += ["", "### Targets (system C)", "", "| Target | Value | Goal | Result |", "|---|---|---|---|"]
        for tname, c in result["targets_check"][name].items():
            label = result["targets"][tname].get("label", tname)
            lines.append(f"| {label} | {_fmt(c['value'])} | {c['op']} {c['target']} | {'met' if c['passed'] else 'missed'} |")
        conf = d["systems"]["C"]["investigation"]["confusion"]
        if conf:
            lines += ["", "### Confusion, system C (expected, then reported)", ""]
            for exp, row in sorted(conf.items()):
                lines.append(f"- {exp}: " + ", ".join(f"{k} {v}" for k, v in sorted(row.items())))
        lines.append("")
    return "\n".join(lines)


def _json_default(o):
    return o.item() if hasattr(o, "item") else str(o)


def write_evaluation(result: dict, store: Path, version: int) -> Path:
    """Write store/eN/{results.json, report.md}; `store` is the evaluations directory."""
    out = Path(store) / f"e{version}"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(result, indent=2, default=_json_default), encoding="utf-8")
    (out / "report.md").write_text(render_report(result), encoding="utf-8")
    return out


def next_version(store: Path) -> int:
    existing = [int(p.name[1:]) for p in Path(store).glob("e*") if p.name[1:].isdigit()]
    return max(existing, default=0) + 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate systems A, B and C on development and held-out data")
    parser.add_argument("--dataset", choices=["dev", "heldout", "both"], default="both")
    parser.add_argument("--version", type=int, default=None, help="evaluation number (default: next)")
    parser.add_argument("--model-store", type=Path, default=BACKEND_DIR / "model_store")
    parser.add_argument("--model", default="v1")
    parser.add_argument("--out", type=Path, default=BACKEND_DIR / "evaluations", help="evaluations directory")
    args = parser.parse_args()

    model = DetectorModel.load(args.model_store / args.model / "model.joblib")
    datasets = default_datasets()
    wanted = {"dev": ["development"], "heldout": ["heldout"], "both": ["development", "heldout"]}[args.dataset]
    result = evaluate(model, {k: datasets[k] for k in wanted})
    version = args.version or next_version(args.out)
    path = write_evaluation(result, args.out, version)
    print(f"Evaluation e{version} written to {path}")


if __name__ == "__main__":
    main()
