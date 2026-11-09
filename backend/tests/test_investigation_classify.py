import numpy as np
import pytest

from app.analysis.frame import ObservableEvent
from app.analysis.model import DetectorModel
from app.analysis.pipeline import analyze_run
from app.investigation.classify import decide, score_categories
from app.investigation.config import DEFAULT_CONFIG as CFG
from app.investigation.evidence import Facts, collect
from app.investigation.grouping import Span, group
from app.investigation.signals import Departure
from app.investigation.localise import localise
from tests.helpers import normal_runs, rep


@pytest.fixture(scope="module")
def model():
    return DetectorModel.fit(normal_runs(10, start_seed=600), normal_runs(4, start_seed=700), n_estimators=60)


def run_case(model, **cfg):
    cfg.setdefault("magnitude", 0.9)
    cfg.setdefault("onset_min", 2)
    run = rep(**cfg)
    out = analyze_run(run, model)
    spans = group(run, out.alerts, out.state, CFG)
    span = next(s for s in spans if s.end >= 24)
    ev, f = collect(run, out, model.reference, span, -1, CFG)
    scores = score_categories(f)
    cls, conf, label, hyps = decide(scores, CFG, ev)
    return cls, conf, label, hyps, localise(cls, f, hyps), ev, scores


def test_unauthorized_valve_close_is_cyber_at_seg05_control(model):
    cls, _, _, _, loc, _, sc = run_case(model, scenario_type="unauthorized_control", method="valve_close",
                                        target_segment="SEG-05", seed=5)
    assert cls == "cyber_manipulation", sc
    assert loc.segment == "SEG-05" and loc.ot_layers == ["control"]


def test_replay_is_cyber_reporting(model):
    cls, _, _, _, loc, _, sc = run_case(model, scenario_type="telemetry_manipulation", method="replay",
                                        target_segment="SEG-03", seed=4)
    assert cls == "cyber_manipulation", sc
    assert loc.segment == "SEG-03" and loc.ot_layers == ["reporting"]


def test_concealed_leak_is_reporting_inconsistency(model):
    cls, _, _, _, loc, _, sc = run_case(model, scenario_type="concealed_physical_incident", method="leak",
                                        target_segment="SEG-04", seed=8)
    assert cls == "reporting_inconsistency", sc
    assert loc.ot_layers == ["physical_process", "reporting"]


def test_erratic_sensor_is_sensor_fault(model):
    cls, _, _, _, loc, _, sc = run_case(model, scenario_type="sensor_fault", method="erratic",
                                        target_segment="SEG-02", seed=2)
    assert cls == "sensor_fault", sc
    assert loc.segment == "SEG-02"


def test_leak_is_physical_anomaly(model):
    cls, _, _, _, _, _, sc = run_case(model, scenario_type="physical_anomaly", method="leak",
                                      target_segment="SEG-04", seed=3)
    assert cls == "physical_anomaly", sc


def test_conflicting_evidence_is_uncertain():
    f = Facts(flagged_segs={"SEG-02"}, single_var_fault_segs={"SEG-02"}, reporting_change_segs={"SEG-02"},
              span_ticks=40)
    f.departures = [Departure('SEG-02', 'valve', 30, 40, 100.0, 50.0)]  # cyber 0.35 + 0.25 vs sensor 0.70
    scores = score_categories(f)
    assert abs(scores["sensor_fault"] - scores["cyber_manipulation"]) < CFG.margin, scores
    cls, conf, label, hyps = decide(scores, CFG)
    assert cls == "uncertain" and len(hyps) == 3 and label in ("Low", "Moderate", "High")
    loc = localise(cls, f, hyps)
    assert loc.segment == "SEG-02" or loc.note.startswith("Not localised")


def test_event_only_span_has_evidence(model):
    run = rep(scenario_type="normal", seed=11)
    run.events.append(ObservableEvent(100, "SEG-05", "Control Layer", "control", "Valve command issued", "no", "high",
                                      "Valve command to 20%"))
    out = analyze_run(run, model)
    span = Span(100, 100, opening_events=[len(run.events) - 1])
    ev, f = collect(run, out, model.reference, span, -1, CFG)
    assert any(e.kind == "control event" for e in ev)
    cls = decide(score_categories(f), CFG, ev)[0]
    assert cls == "cyber_manipulation"
