import dataclasses
import json

import pytest

from app.analysis.frame import ReportedRun
from app.analysis.model import DetectorModel
from app.analysis.pipeline import analyze_run
from app.investigation import investigate
from tests.helpers import normal_runs, rep


@pytest.fixture(scope="module")
def model():
    return DetectorModel.fit(normal_runs(10, start_seed=600), normal_runs(4, start_seed=700), n_estimators=60)


def _run(model, **cfg):
    cfg.setdefault("magnitude", 0.9)
    cfg.setdefault("onset_min", 2)
    run = rep(**cfg)
    out = analyze_run(run, model)
    return run, out, investigate(run, out, model.reference)


def test_investigate_unauthorized_control_story(model):
    _, _, incs = _run(model, scenario_type="unauthorized_control", method="valve_close", target_segment="SEG-05", seed=5)
    inc = next(i for i in incs if i.classification == "cyber_manipulation")
    stages = [c.stage for c in inc.chain]
    assert len(stages) >= 3 and "action" in stages and "process" in stages
    assert "T0855" in [t.technique_id for t in inc.mitre]
    assert inc.actions
    assert "caused" not in inc.summary.lower() and "attacker" not in inc.summary.lower()


def test_no_chain_for_sensor_fault(model):
    _, _, incs = _run(model, scenario_type="sensor_fault", method="erratic", target_segment="SEG-02", seed=3)
    inc = next(i for i in incs if i.classification == "sensor_fault")
    assert inc.chain == [] and inc.mitre == []


def test_normal_run_without_flags_has_no_incidents(model):
    from app.investigation.signals import is_opening_event
    for seed in range(300, 341):
        run = rep(scenario_type="normal", seed=seed)
        out = analyze_run(run, model)
        if not out.alerts and not any(is_opening_event(e) for e in run.events):
            assert investigate(run, out, model.reference) == []
            return
    pytest.fail("no clean normal run in seeds 300-340")


def test_truncated_equals_prefix(model):
    run = rep(scenario_type="telemetry_manipulation", method="replay", target_segment="SEG-03", seed=4, magnitude=0.9, onset_min=2)
    k = 81
    tr = ReportedRun(pressure=run.pressure[:k], flow=run.flow[:k], temperature=run.temperature[:k],
                     valve_open=run.valve_open[:k], pump_speed=run.pump_speed[:k],
                     events=[e for e in run.events if e.tick <= 80])
    out = analyze_run(tr, model)
    for inc in investigate(tr, out, model.reference):
        assert inc.end_tick <= 80
        assert all(e.tick <= 80 and e.end_tick <= 80 for e in inc.evidence)


def test_to_dict_is_json_serialisable(model):
    _, _, incs = _run(model, scenario_type="unauthorized_control", method="valve_close", target_segment="SEG-05", seed=5)
    assert incs
    json.dumps(incs[0].to_dict())


def test_event_only_incident_has_severity_and_rail_data(model):
    run = rep(scenario_type="unauthorized_control", method="valve_close", target_segment="SEG-05", seed=5,
              magnitude=0.9, onset_min=2)
    out = dataclasses.replace(analyze_run(run, model), alerts=[])
    incs = investigate(run, out, model.reference)
    assert len(incs) == 1
    inc = incs[0]
    assert inc.severity in {"medium", "high", "critical"} and inc.windows == []
    assert any(e.link.get("type") == "event" and e.supports.get("cyber_manipulation", 0) >= 0.5 for e in inc.evidence)
