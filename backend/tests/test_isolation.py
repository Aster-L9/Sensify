"""The analysis must never see ground truth (mock-data README; spec §2)."""
import ast
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "app" / "analysis"
BANNED_MODULES = {"app.models", "app.sim.engine", "app.sim.scenarios", "ml"}
BANNED_NAMES = {"GroundTruthTelemetry", "ScenarioGroundTruth", "RunData"}
INVESTIGATION_DIR = Path(__file__).resolve().parent.parent / "app" / "investigation"
INVESTIGATION_BANNED = BANNED_MODULES | {"app.database", "app.services"}


def test_investigation_package_never_imports_ground_truth():
    files = list(INVESTIGATION_DIR.glob("*.py"))
    assert files, "investigation package not found"
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", None) or ""
                modules = [module] + [a.name for a in node.names]
                assert not any(m == b or m.startswith(b + ".") for m in modules for b in INVESTIGATION_BANNED), path
                assert not BANNED_NAMES & {a.name for a in node.names}, path


def test_analysis_package_never_imports_ground_truth():
    files = list(ANALYSIS_DIR.glob("*.py"))
    assert files, "analysis package not found"
    for path in files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, "module", None) or ""
                modules = [module] + [a.name for a in node.names]
                assert not any(m == b or m.startswith(b + ".") for m in modules for b in BANNED_MODULES), path
                assert not BANNED_NAMES & {a.name for a in node.names}, path
