"""
Validation outcomes for a model version trained before they were recorded (handover DH-09).

    python -m ml.validation_metrics --version 1

Scores the validation split with the stored model and writes model_store/vN/validation.json
beside the existing files (nothing is overwritten; the model file is only read). The app
attaches it to the registered version at startup. The provenance says it was computed after
training; the test-split metrics are unchanged.
"""
import argparse
import json
from pathlib import Path

from app.analysis.model import DetectorModel
from ml.dataset import load_dataset, split
from ml.train import DEFAULT_DATASET, DEFAULT_STORE, validation_section


def write_validation(version: int, dataset_dir: Path = DEFAULT_DATASET, store_dir: Path = DEFAULT_STORE) -> Path:
    version_dir = Path(store_dir) / f"v{version}"
    target = version_dir / "validation.json"
    if target.exists():
        raise FileExistsError(f"{target} already exists; delete it first to recompute")
    doc = json.loads((version_dir / "metrics.json").read_text(encoding="utf-8"))
    if doc.get("validation"):
        raise ValueError(f"v{version} already recorded validation outcomes at training")
    model = DetectorModel.load(version_dir / "model.joblib")
    model.version = version
    runs = split(load_dataset(Path(dataset_dir)), "validation")
    section = validation_section(model, runs, Path(dataset_dir), computed="after training")
    target.write_text(json.dumps(section, indent=2), encoding="utf-8")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Record validation outcomes for an existing model version")
    parser.add_argument("--version", type=int, required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    args = parser.parse_args()
    print(f"Wrote {write_validation(args.version, args.dataset, args.store)}")


if __name__ == "__main__":
    main()
