"""
Training pipeline: dataset -> features -> per-segment Isolation Forests ->
calibration -> evaluation on the held-out test split -> versioned artifact.

    python -m ml.train [--generate] [--trees 150] [--samples 256] [--alpha 0.005] [--version N]

Writes model_store/vN/{model.joblib, metrics.json, report.md, manifest.json}.
"""
import argparse
import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.analysis.features import FEATURE_SPEC_VERSION
from app.analysis.model import DetectorModel
from app.analysis.pipeline import analyze_run
from ml.dataset import load_dataset, split
from ml.metrics import compare_targets, detection_metrics, trust_metrics

ML_DIR = Path(__file__).resolve().parent
DEFAULT_DATASET = ML_DIR / "data"
DEFAULT_STORE = ML_DIR.parent / "model_store"
TARGETS_PATH = ML_DIR / "targets.json"
ALGORITHM = "isolation_forest"


@dataclass
class TrainParams:
    n_estimators: int = 150
    max_samples: int = 256
    alpha: float = 0.004
    random_state: int = 2026


@dataclass
class TrainResult:
    version: int
    version_dir: Path
    metrics: dict
    targets_check: dict
    trained_seconds: float
    dataset_summary: dict


def next_version(store_dir: Path) -> int:
    existing = [int(p.name[1:]) for p in Path(store_dir).glob("v*") if p.name[1:].isdigit()]
    return max(existing, default=0) + 1


def load_targets() -> dict:
    return json.loads(TARGETS_PATH.read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    """A project-relative path for reports; never the server's absolute path."""
    try:
        return Path(path).resolve().relative_to(ML_DIR.parent.resolve()).as_posix()
    except ValueError:
        return Path(path).name


def _dataset_summary(runs, dataset_dir: Path) -> dict:
    summary = {"path": _display_path(dataset_dir), "runs": len(runs), "splits": {}}
    for r in runs:
        by_type = summary["splits"].setdefault(r.split, {})
        by_type[r.scenario_type] = by_type.get(r.scenario_type, 0) + 1
    return summary


def train_model(params: TrainParams, dataset_dir: Path, store_dir: Path, version: int,
                generate_if_missing: bool = True, progress: Callable[[str], None] | None = None) -> TrainResult:
    started = time.perf_counter()
    say = progress or (lambda message: None)
    dataset_dir, store_dir = Path(dataset_dir), Path(store_dir)

    if not (dataset_dir / "runs.csv").exists():
        if not generate_if_missing:
            raise FileNotFoundError(f"No dataset found at {dataset_dir}")
        from ml.generate_dataset import generate_dataset
        say("Generating the mock dataset")
        generate_dataset(dataset_dir)

    say("Loading the dataset")
    runs = load_dataset(dataset_dir)
    train = [r for r in split(runs, "train") if r.scenario_type == "normal"]
    val_normal = [r for r in split(runs, "validation") if r.scenario_type == "normal"]
    test = split(runs, "test")
    if not train or not val_normal or not test:
        raise ValueError("The dataset needs normal train runs, normal validation runs and a test split")

    say(f"Training on {len(train)} normal runs")
    model = DetectorModel.fit([r.reported for r in train], [r.reported for r in val_normal],
                              n_estimators=params.n_estimators, max_samples=params.max_samples,
                              alpha=params.alpha, random_state=params.random_state)
    model.version = version

    say(f"Evaluating on {len(test)} held-out test runs")
    flags, scores, baseline, trust = {}, {}, {}, {}
    for run in test:
        out = analyze_run(run.reported, model)
        flags[run.run_id], scores[run.run_id] = out.ml_flag, out.scores
        baseline[run.run_id], trust[run.run_id] = out.baseline.any, out.trust.status
    metrics = {
        "ml": detection_metrics(flags, test, scores),
        "baseline": detection_metrics(baseline, test),
        "trust": trust_metrics(trust, test),
    }
    targets = load_targets()
    check = compare_targets(metrics, targets)
    trained_seconds = round(time.perf_counter() - started, 2)
    summary = _dataset_summary(runs, dataset_dir)

    version_dir = store_dir / f"v{version}"
    version_dir.mkdir(parents=True, exist_ok=True)
    model.save(version_dir / "model.joblib")
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    document = {"version": version, "algorithm": ALGORITHM, "feature_spec": FEATURE_SPEC_VERSION,
                "params": asdict(params), "dataset": summary, "metrics": metrics, "targets": targets,
                "targets_check": check, "trained_seconds": trained_seconds, "created_at": created_at}
    (version_dir / "metrics.json").write_text(json.dumps(document, indent=2), encoding="utf-8")
    passed = sum(c["passed"] for c in check.values())
    manifest = {
        "version": version, "algorithm": ALGORITHM, "feature_spec": FEATURE_SPEC_VERSION,
        "params": asdict(params), "created_at": created_at, "trained_seconds": trained_seconds,
        "headline": {
            "detection_rate": metrics["ml"]["overall"]["rate"],
            "tick_false_alarm_rate": metrics["ml"]["false_alarm"]["tick_rate"],
            "false_windows_per_run": metrics["ml"]["false_alarm"]["windows_per_run"],
            "window_precision": metrics["ml"]["window_precision"],
            "median_time_to_detect_s": metrics["ml"]["time_to_detect_s"]["median"],
            "targets_passed": f"{passed}/{len(check)}",
        },
    }
    (version_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (version_dir / "report.md").write_text(render_report(document), encoding="utf-8")
    say(f"Saved model v{version} ({passed}/{len(check)} targets met)")
    return TrainResult(version, version_dir, metrics, check, trained_seconds, summary)


def _pct(value) -> str:
    """Percent with one decimal, or three when the rate is under 1 % so it never reads as 0.0 %."""
    if value is None:
        return "n/a"
    return f"{value * 100:.3f} %" if 0 < abs(value) < 0.01 else f"{value * 100:.1f} %"


def _num(value, unit: str = "", digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}{unit}"


def render_report(doc: dict) -> str:
    ml, base, trust = doc["metrics"]["ml"], doc["metrics"]["baseline"], doc["metrics"]["trust"]
    lines = [
        f"# Sensify anomaly model v{doc['version']}",
        "",
        f"Trained {doc['created_at']} in {doc['trained_seconds']} s. Algorithm: per-segment Isolation Forest "
        f"(feature spec `{doc['feature_spec']}`), trained only on normal runs; evaluated on the held-out test split.",
        "",
        "## Parameters",
        "",
        *(f"- `{k}`: {v}" for k, v in doc["params"].items()),
        "",
        "## Dataset",
        "",
        "| Split | Runs by scenario type |",
        "|---|---|",
        *(f"| {s} | {', '.join(f'{t}: {n}' for t, n in sorted(by.items()))} |" for s, by in doc["dataset"]["splits"].items()),
        "",
        "## Targets",
        "",
        "| Target | Value | Goal | Met |",
        "|---|---|---|---|",
    ]
    for name, c in doc["targets_check"].items():
        label = doc["targets"][name].get("label", name)
        value = c["value"]
        shown = "n/a" if value is None else (f"{value:.4g}" if isinstance(value, float) else str(value))
        lines.append(f"| {label} | {shown} | {c['op']} {c['target']} | {'yes' if c['passed'] else '**no**'} |")
    lines += [
        "",
        "## Detection by scenario type (ML vs threshold baseline)",
        "",
        "| Scenario type | ML detected | Threshold baseline detected |",
        "|---|---|---|",
    ]
    for t, v in ml["per_type"].items():
        b = base["per_type"].get(t, {"detected": 0, "total": 0, "rate": None})
        lines.append(f"| {t} | {v['detected']}/{v['total']} ({_pct(v['rate'])}) | {b['detected']}/{b['total']} ({_pct(b['rate'])}) |")
    lines += [
        "",
        "## Other measures",
        "",
        "| Measure | ML | Threshold baseline |",
        "|---|---|---|",
        f"| Overall detection rate | {_pct(ml['overall']['rate'])} | {_pct(base['overall']['rate'])} |",
        f"| Median / p90 time to detect | {_num(ml['time_to_detect_s']['median'], ' s', 0)} / {_num(ml['time_to_detect_s']['p90'], ' s', 0)} "
        f"| {_num(base['time_to_detect_s']['median'], ' s', 0)} / {_num(base['time_to_detect_s']['p90'], ' s', 0)} |",
        f"| Tick false-alarm rate (normal runs) | {_pct(ml['false_alarm']['tick_rate'])} | {_pct(base['false_alarm']['tick_rate'])} |",
        f"| False alert windows per normal run | {_num(ml['false_alarm']['windows_per_run'])} | {_num(base['false_alarm']['windows_per_run'])} |",
        f"| Window precision | {_pct(ml['window_precision'])} | {_pct(base['window_precision'])} |",
        f"| Localization hit rate | {_pct(ml['localization_hit_rate'])} | {_pct(base['localization_hit_rate'])} |",
        f"| ROC-AUC (segment-tick) | {_num(ml['roc_auc'], '', 3)} | n/a |",
        "",
        "## Telemetry trust",
        "",
        f"- Compromised-reporting runs where the target lost trust: {_pct(trust['compromise_detection_rate'])} "
        f"({trust['compromised_runs']} runs)",
        f"- Low-trust rate on honest runs: {_pct(trust['low_trust_rate_honest'])}",
        "",
        "Missed targets are reported as missed. Scenario labels were used only to compute these figures.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate a Sensify anomaly model")
    parser.add_argument("--generate", action="store_true", help="regenerate the mock dataset first")
    parser.add_argument("--trees", type=int, default=150)
    parser.add_argument("--samples", type=int, default=256)
    parser.add_argument("--alpha", type=float, default=0.004, help="target tick false-alarm rate for calibration")
    parser.add_argument("--version", type=int, default=None)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--register", action="store_true", help="register the new version in the app database")
    parser.add_argument("--activate", action="store_true", help="register and make it the active model")
    args = parser.parse_args()

    if args.generate:
        from ml.generate_dataset import generate_dataset
        print("Generating the mock dataset ...")
        generate_dataset(args.dataset)
    version = args.version or next_version(args.store)
    result = train_model(TrainParams(args.trees, args.samples, args.alpha), args.dataset, args.store, version,
                         progress=lambda m: print(f"- {m}"))
    print(f"\nModel v{result.version} written to {result.version_dir} in {result.trained_seconds} s")
    for name, c in result.targets_check.items():
        print(f"  {'PASS' if c['passed'] else 'MISS'}  {name}: {c['value']} (goal {c['op']} {c['target']})")
    if args.register or args.activate:
        from app.database import Base, SessionLocal, engine
        from app.migrate import migrate_if_needed
        from app.services.registry import register_from_dir

        migrate_if_needed(engine)
        Base.metadata.create_all(engine)
        db = SessionLocal()
        try:
            register_from_dir(db, result.version_dir, None, activate_now=args.activate)
        finally:
            db.close()
        print(f"Registered model v{result.version}{' and made it active' if args.activate else ''}")


if __name__ == "__main__":
    main()
