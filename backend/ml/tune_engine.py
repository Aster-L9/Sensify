"""
Engine tuning on the validation split (design §6.6) and the frozen-decisions snapshot.
Only the validation split is used.
"""
import argparse
import dataclasses
import itertools
import json
from pathlib import Path

from app.analysis.model import DetectorModel
from app.analysis.pipeline import analyze_run
from app.investigation.config import DEFAULT_CONFIG, ENGINE_VERSION, EngineConfig
from app.investigation.engine import investigate
from ml.dataset import DatasetRun, load_dataset, split
from ml.incident_metrics import RunLabel, _event_incident, dev_labels, incident_criteria

ML_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ML_DIR.parent
SNAPSHOT_PATH = BACKEND_DIR / "tests" / "data" / "engine_i2_snapshot.json"
MODEL_PATH = BACKEND_DIR / "model_store" / "v1" / "model.joblib"

MIN_SCORES = (0.35, 0.45, 0.55)
MARGINS = (0.10, 0.15, 0.20)
GAP_TICKS = (24, 36, 48)


def load_validation() -> tuple[list[DatasetRun], dict[str, RunLabel]]:
    runs = split(load_dataset(ML_DIR / "data"), "validation")
    return runs, dev_labels(runs)


def _rate(metric) -> float:
    if isinstance(metric, dict):
        metric = metric.get("rate")
    return 0.0 if metric is None else float(metric)


def _analyse(model: DetectorModel, runs: list[DatasetRun]) -> dict:
    return {r.run_id: analyze_run(r.reported, model) for r in runs}


def _incidents(model, runs, outs, cfg) -> dict[str, list[dict]]:
    return {r.run_id: [i.summary_row() for i in investigate(r.reported, outs[r.run_id], model.reference, cfg)]
            for r in runs}


def tune(model: DetectorModel, runs: list[DatasetRun], labels: dict[str, RunLabel]) -> list[dict]:
    outs = _analyse(model, runs)
    rows = []
    for ms, mg, gap in itertools.product(MIN_SCORES, MARGINS, GAP_TICKS):
        cfg = dataclasses.replace(DEFAULT_CONFIG, min_score=ms, margin=mg, gap_ticks=gap)
        m = incident_criteria(_incidents(model, runs, outs, cfg), runs, labels, can_classify=True)
        acc = _rate(m["classification_accuracy"])
        cov = _rate(m["decision_coverage"])
        unexp = _rate(m["unexplained_per_normal_run"])
        rows.append({"min_score": ms, "margin": mg, "gap_ticks": gap,
                     "accuracy": acc, "coverage": cov, "unexplained_per_normal_run": unexp,
                     "incident_detection": _rate(m["incident_detection"]),
                     "objective": acc + 0.5 * cov - 0.5 * unexp})
    rows.sort(key=lambda r: r["objective"], reverse=True)
    return rows


def snapshot(model: DetectorModel, runs: list[DatasetRun], labels: dict[str, RunLabel],
             cfg: EngineConfig = DEFAULT_CONFIG) -> dict:
    outs = _analyse(model, runs)
    incs = _incidents(model, runs, outs, cfg)
    result = {}
    for r in runs:
        if r.scenario_type == "normal":
            result[r.run_id] = {"classification": [i["classification"] for i in incs[r.run_id]],
                                "segment": [i.get("segment_code") for i in incs[r.run_id]]}
            continue
        ev = _event_incident(r, incs[r.run_id], True)
        result[r.run_id] = {"classification": ev["classification"] if ev else None,
                            "segment": ev.get("segment_code") if ev else None}
    return {"engine_version": ENGINE_VERSION, "config": dataclasses.asdict(cfg), "runs": result}


def main() -> None:
    parser = argparse.ArgumentParser(description="Tune the investigation engine on the validation split")
    parser.add_argument("--write-snapshot", action="store_true")
    args = parser.parse_args()
    model = DetectorModel.load(MODEL_PATH)
    runs, labels = load_validation()
    rows = tune(model, runs, labels)
    print(f"{'min_score':>9} {'margin':>6} {'gap':>4} {'acc':>6} {'cov':>6} {'unexpl':>6} {'obj':>6}")
    for r in rows[:10]:
        print(f"{r['min_score']:>9.2f} {r['margin']:>6.2f} {r['gap_ticks']:>4} {r['accuracy']:>6.3f} "
              f"{r['coverage']:>6.3f} {r['unexplained_per_normal_run']:>6.3f} {r['objective']:>6.3f}")
    if args.write_snapshot:
        snap = snapshot(model, runs, labels)
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(json.dumps(snap, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Snapshot written to {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
