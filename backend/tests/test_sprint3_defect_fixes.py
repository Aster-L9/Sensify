"""Regression tests for the Sprint 3 defects found in testing (D01-D05, D07, D08, D10, D13)."""
import csv
import io
from datetime import datetime
from types import SimpleNamespace

import pytest
from fpdf import FPDF

from app.investigation import narrative as nar
from app.investigation.classify import decide
from app.investigation.config import DEFAULT_CONFIG as CFG
from app.investigation.evidence import Facts
from app.investigation.types import CATEGORIES, EvidenceItem, Hypothesis, Localisation
from app.reports.csv_export import evaluation_rows, incident_csv
from app.reports.pdf import evaluation_pdf, incident_pdf

LOC = Localisation("SEG-03", ["reporting"], "")
RUN = SimpleNamespace(id=9, name="Run 9", started_at=datetime(2026, 1, 1), tick_seconds=5)


def _text(monkeypatch, build) -> str:
    """Everything written to the PDF, captured on its way in."""
    seen = []
    for name in ("cell", "multi_cell"):
        def spy(self, w=None, h=None, text="", *args, _real=getattr(FPDF, name), **kw):
            seen.append(str(text))
            return _real(self, w, h, text, *args, **kw)
        monkeypatch.setattr(FPDF, name, spy)
    assert build().startswith(b"%PDF")
    return " ".join(seen)


def _scores(top: float, second: float) -> dict:
    s = dict.fromkeys(CATEGORIES, 0.0)
    s["cyber_manipulation"], s["sensor_fault"] = top, second
    return s


@pytest.mark.parametrize("top,second", [(0.80, 0.65), (0.60, 0.45), (0.55, 0.40), (0.35, 0.20)])
def test_a_margin_of_exactly_015_is_decided(top, second):
    assert decide(_scores(top, second), CFG)[0] == "cyber_manipulation"


def test_a_margin_below_015_is_uncertain():
    assert decide(_scores(0.60, 0.46), CFG)[0] == "uncertain"


def _item(eid: str, kind: str, tick: int = 5, observation: str = "o") -> EvidenceItem:
    return EvidenceItem(eid, kind, tick, tick, "SEG-03", observation, "i", {}, {})


def test_one_evidence_item_cannot_form_a_chain():
    assert nar.chain("cyber_manipulation", Facts(), [_item("E1", "telemetry anomaly")]) == []


def test_two_evidence_items_can_form_a_chain():
    stages = nar.chain("reporting_inconsistency", Facts(), [_item("E1", "telemetry anomaly"), _item("E2", "trust drop", 6)])
    assert {s.stage for s in stages} == {"process", "visibility", "detection"}


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_check_gives_its_reason(category):
    for facts in (Facts(), Facts(replay_segs={"SEG-03"})):
        lines = nar.actions(category, LOC, facts)
        assert lines[-1] == nar.NO_CONTROL_LINE and len(lines) > 1
        assert all(", because " in line for line in lines[:-1]), lines


def test_replay_checks_do_not_refer_to_a_command():
    lines = nar.actions("cyber_manipulation", LOC, Facts(replay_segs={"SEG-03"}))[:-1]
    assert not [x for x in lines if "command" in x.lower() or "workstation" in x.lower()]


def test_uncertain_checks_do_not_refer_to_an_absent_command():
    hyps = [Hypothesis("cyber_manipulation", 0.5, []), Hypothesis("sensor_fault", 0.45, [])]
    assert "command" not in " ".join(nar.actions("uncertain", LOC, Facts(replay_segs={"SEG-03"}), hyps)[:-1]).lower()


def test_command_checks_stay_when_a_command_exists():
    event = SimpleNamespace(event_type="valve_close", segment="SEG-03", tick=4)
    assert any("workstation that sent the command" in x for x in nar.actions("cyber_manipulation", LOC, Facts(unauth_cmds=[event])))


UNCERTAIN = {
    "key": "9-1", "status": "investigating", "status_note": None, "classification": "uncertain", "confidence": 0.44,
    "confidence_label": "Low", "severity": "high", "summary": "Fits both.",
    "localisation": {"segment": None, "ot_layers": [], "note": "Not localised: no evidence"},
    "hypotheses": [{"category": "sensor_fault", "score": 0.55, "evidence_ids": ["E1"]},
                   {"category": "physical_anomaly", "score": 0.5, "evidence_ids": ["E1", "E2"]}],
    "uncertainty": {"hypotheses": ["sensor_fault", "physical_anomaly"],
                    "discriminators": ["Whether a handheld instrument agrees with the reading"]},
    "timeline": [{"tick": 29, "segment": "SEG-02", "kind": "trust drop", "observation": "Trust fell",
                  "interpretation": "Worth a look", "evidence_id": "E1"}],
    "chain": [{"stage": "process", "label": "Process change", "tick": 29, "segment": "SEG-02", "evidence_ids": ["E1"]}],
    "mitre": [{"technique_id": "T0829", "name": "Loss of View", "tactic": "Impact", "reason": "r"}],
    "evidence": [{"id": "E1", "kind": "trust drop", "tick": 29, "segment": "SEG-02", "observation": "Trust fell",
                  "interpretation": "Worth a look"}],
    "actions": ["Check the gauge, because it is local."],
}


def test_incident_pdf_shows_what_the_page_shows(monkeypatch):
    text = _text(monkeypatch, lambda: incident_pdf(UNCERTAIN, RUN, "Uncertain"))
    for expected in ("confidence 44 % Low", "segment Not localised", "Timeline", "T+02:25", "Why Sensify is uncertain",
                     "Sensor/device fault: score 55 %", "Possible physical/process anomaly: score 50 %",
                     "What would tell them apart", "Whether a handheld instrument agrees with the reading"):
        assert expected in text, expected
    assert "2026-01-01" not in text


def test_incident_csv_holds_every_section():
    rows = list(csv.DictReader(io.StringIO(incident_csv(UNCERTAIN, RUN, "Uncertain"))))
    assert {r["section"] for r in rows} == {"incident", "hypothesis", "discriminator", "timeline", "chain", "mitre",
                                            "evidence", "check"}
    fields = {r["kind"]: r["observation"] for r in rows if r["section"] == "incident"}
    assert fields["classification"] == "Uncertain" and fields["confidence"] == "44 % Low"
    assert fields["segment"] == "Not localised" and fields["severity"] == "high" and fields["status"] == "investigating"


def _evaluation() -> dict:
    conf = {"sensor_fault": {"sensor_fault": 12, "uncertain": 4}, "cyber_manipulation": {"cyber_manipulation": 26}}
    sysdoc = {"detection": {"overall": {"rate": 0.9}, "false_alarm": {"tick_rate": 0.0003}},
              "investigation": {"classification_accuracy": {"rate": 0.75}, "confusion": conf}}
    return {"model_version": 1, "engine_version": "i2",
            "datasets": {"development": {"systems": {"A": {"detection": sysdoc["detection"], "investigation": {}},
                                                     "C": sysdoc}}},
            "targets_check": {"development": {"detection_rate": {"value": 0.9, "target": 0.9, "op": ">=", "passed": True},
                                              "tick_false_alarm_rate": {"value": 0.002, "target": 0.001, "op": "<=", "passed": False}}}}


def test_evaluation_pdf_uses_page_labels_and_shows_matrix_and_charts(monkeypatch):
    text = _text(monkeypatch, lambda: evaluation_pdf(SimpleNamespace(version=1), _evaluation()))
    for expected in ("Event detection rate", "90.0 %", "Event detection rate: 90.0 % (target at least 90.0 %) Met",
                     "(target at most 0.1 %) Missed", "Charts", "Confusion matrix for C: Development", "Expected / reported"):
        assert expected in text, expected
    assert "tick_false_alarm_rate" not in text


def test_evaluation_csv_holds_the_confusion_matrix():
    rows = evaluation_rows(_evaluation())
    assert ["development", "C", "confusion:sensor_fault->uncertain", 4, "", ""] in rows


def test_unknown_filter_values_are_rejected(client, analyst_headers):
    for query in ("classification=nonsense", "status=closed", "severity=extreme"):
        assert client.get(f"/incidents?{query}", headers=analyst_headers).status_code == 422, query


def test_known_filter_values_are_accepted(client, analyst_headers):
    for query in ("classification=uncertain", "status=developing", "status=resolved", "severity=low"):
        assert client.get(f"/incidents?{query}", headers=analyst_headers).status_code == 200, query


def _has_key(doc, key: str) -> bool:
    if isinstance(doc, dict):
        return key in doc or any(_has_key(v, key) for v in doc.values())
    return any(_has_key(v, key) for v in doc) if isinstance(doc, list) else False


def test_scenario_rates_are_admin_only_in_evaluations(client, admin_headers, analyst_headers):
    analyst = client.get("/evaluation/latest", headers=analyst_headers).json()
    admin = client.get("/evaluation/latest", headers=admin_headers).json()
    assert _has_key(admin["results"], "per_type") and not _has_key(analyst["results"], "per_type")
    detection = analyst["results"]["datasets"]["development"]["systems"]["C"]["detection"]
    assert detection["per_type_min_rate"] is not None


def test_scenario_rates_are_admin_only_in_evaluation_csv(client, admin_headers, analyst_headers):
    analyst = client.get("/reports/evaluation/1?format=csv", headers=analyst_headers).text
    admin = client.get("/reports/evaluation/1?format=csv", headers=admin_headers).text
    assert ",detection_rate:" in admin and ",detection_rate:" not in analyst


def test_scenario_rates_are_admin_only_in_model_detail(client, admin_headers, analyst_headers, tiny_model):
    v1 = next(m for m in client.get("/models", headers=admin_headers).json() if m["version"] == 1)
    admin = client.get(f"/models/{v1['id']}", headers=admin_headers).json()
    analyst = client.get(f"/models/{v1['id']}", headers=analyst_headers).json()
    assert _has_key(admin, "per_type")
    for key in ("per_type", "by_type", "splits"):
        assert not _has_key(analyst, key), key
    assert analyst["metrics"]["ml"]["overall"] == admin["metrics"]["ml"]["overall"]
