"""The analysis must never see ground truth: it reads only reported telemetry."""
import ast
from pathlib import Path

ANALYSIS_DIR = Path(__file__).resolve().parent.parent / "app" / "analysis"
BANNED_MODULES = {"app.models", "app.sim.engine", "app.sim.scenarios", "ml"}
BANNED_NAMES = {"GroundTruthTelemetry", "ScenarioGroundTruth", "RunData"}


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
