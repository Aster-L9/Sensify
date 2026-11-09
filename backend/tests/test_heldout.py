import ast
from pathlib import Path

import pandas as pd

from ml.dataset import load_dataset

BACKEND = Path(__file__).resolve().parents[1]
HELDOUT = BACKEND / "ml" / "heldout"


def test_generator_is_isolated():
    tree = ast.parse((BACKEND / "ml" / "generate_heldout.py").read_text(encoding="utf-8"))
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert names
    assert not [n for n in names if n.startswith(("app.analysis", "app.investigation"))]


def test_heldout_files_load():
    runs = load_dataset(HELDOUT)
    assert len(runs) == 72
    assert {r.split for r in runs} == {"heldout"}


def test_labels_cover_ambiguous_and_ranges():
    labels = pd.read_csv(HELDOUT / "labels.csv", keep_default_na=False)
    assert len(labels) == 72
    assert (labels["ambiguous"].astype(str).str.lower() == "true").sum() >= 18
    runs = pd.read_csv(HELDOUT / "runs.csv")
    scen = runs[runs["scenario_type"] != "normal"]
    assert len(scen) == 60
    assert ((scen["magnitude"] <= 0.3) & (scen["magnitude"] >= 0.1)).all()
    assert (scen["recovery"] == False).sum() >= 30  # noqa: E712
