from pathlib import Path

from fpdf import FPDF

from app.investigation.types import CATEGORY_LABELS, OT_LAYER_LABELS
from app.reports.csv_export import NA, confidence_text, system_criteria

FONTS = Path(__file__).resolve().parent / "fonts"
NOT_LOCALISED = "Not localised"

# Evaluation page labels and formats, keyed by the criterion names in system_criteria.
CRITERIA = {
    "detection_rate": ("Event detection rate", "pct"),
    "detection_rate_per_type_min": ("Detection rate, lowest scenario type", "pct"),
    "tick_false_alarm_rate": ("Tick false-alarm rate on normal runs", "pct"),
    "false_windows_per_run": ("False alert windows per normal run", "per_run"),
    "window_precision": ("Window precision", "pct"),
    "time_to_detect_median_s": ("Median time to detect", "sec"),
    "localization_hit_rate": ("Localisation hit rate", "pct"),
    "incident_detection": ("Incident detection", "pct"),
    "classification_accuracy": ("Classification accuracy", "pct"),
    "decision_coverage": ("Decision coverage", "pct"),
    "ambiguity_handled": ("Ambiguous runs with an acceptable outcome", "pct"),
    "segment_localisation": ("Segment localisation", "pct"),
    "ot_layer_accuracy": ("OT layer accuracy", "pct"),
    "incidents_per_normal_run": ("Incidents per normal run", "per_run"),
    "unexplained_per_normal_run": ("Unexplained incidents per normal run", "per_run"),
    "incidents_outside_event": ("Incidents outside the event", "count"),
}
TARGETS = {
    "detection_rate": ("Event detection rate", "pct"),
    "detection_rate_per_type": ("Detection rate, lowest scenario type", "pct"),
    "tick_false_alarm_rate": ("Tick false-alarm rate on normal runs", "pct"),
    "false_windows_per_run": ("False alert windows per normal run", "per_run"),
    "window_precision": ("Window precision", "pct"),
    "median_time_to_detect": ("Median time to detect", "sec"),
    "trust_compromise_detection": ("Compromised reporting caught (trust)", "pct"),
    "trust_false_low_rate": ("Honest readings wrongly doubted (trust)", "pct"),
    "incident_detection": ("Incident detection", "pct"),
    "classification_accuracy": ("Classification accuracy", "pct"),
    "decision_coverage": ("Decision coverage", "pct"),
    "ambiguity_handled": ("Ambiguous runs with an acceptable outcome", "pct"),
    "segment_localisation": ("Segment localisation", "pct"),
    "ot_layer_accuracy": ("OT layer accuracy", "pct"),
    "unexplained_per_normal_run": ("Unexplained incidents per normal run", "per_run"),
}
CHART_CRITERIA = ["detection_rate", "window_precision", "incident_detection", "classification_accuracy",
                  "segment_localisation", "ot_layer_accuracy"]
CLASSIFICATION_ONLY = {"classification_accuracy", "ot_layer_accuracy"}  # not available for A and B
DATASET_TITLES = {"development": "Development", "heldout": "Held-out"}
CONFUSION_NAMES = {"normal_behaviour": "Normal", "physical_anomaly": "Physical", "sensor_fault": "Sensor",
                   "cyber_manipulation": "Cyber", "reporting_inconsistency": "Reporting", "uncertain": "Uncertain"}


def _pdf() -> FPDF:
    pdf = FPDF()
    pdf.add_font("DejaVu", "", str(FONTS / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONTS / "DejaVuSans-Bold.ttf"))
    pdf.set_auto_page_break(True, 15)
    pdf.add_page()
    return pdf


def _h(pdf, text, size=14):
    pdf.set_font("DejaVu", "B", size)
    pdf.multi_cell(0, 7, str(text), new_x="LMARGIN", new_y="NEXT")


def _p(pdf, text, size=10):
    pdf.set_font("DejaVu", "", size)
    pdf.multi_cell(0, 5.5, str(text), new_x="LMARGIN", new_y="NEXT")


def fmt_value(v) -> str:
    if isinstance(v, dict):
        v = v.get("rate")
    if v is None:
        return NA
    if isinstance(v, bool) or isinstance(v, int) or not isinstance(v, float):
        return str(v)
    return f"{v:.5f}" if 0 < abs(v) < 0.01 else f"{v:.3f}"


def fmt_metric(v, kind: str) -> str:
    """A value as the evaluation page shows it."""
    if isinstance(v, dict):
        v = v.get("rate")
    if v is None:
        return NA
    if kind == "sec":
        return f"{round(v)} s"
    if kind == "per_run":
        return f"{v:.2f}"
    if kind == "count":
        return str(v)
    p = v * 100
    return f"{p:.{2 if p and abs(p) < 0.1 else 1}f} %"


def _mmss(run, tick) -> str:
    secs = int((tick or 0) * run.tick_seconds)
    return f"T+{secs // 60:02d}:{secs % 60:02d}"


def incident_pdf(d: dict, run, label: str) -> bytes:
    pdf = _pdf()
    _h(pdf, f"Incident {d['key']}", 16)
    _p(pdf, f"{label} | confidence {confidence_text(d)} | severity {d['severity']}")
    _p(pdf, f"Run: {run.name} | segment {d['localisation'].get('segment') or NOT_LOCALISED} | status {d['status']}")
    pdf.ln(2)
    _p(pdf, d.get("summary", ""))
    pdf.ln(2)
    loc = d.get("localisation") or {}
    _h(pdf, "Location", 12)
    layers = ", ".join(OT_LAYER_LABELS.get(x, x) for x in loc.get("ot_layers") or []) or NA
    _p(pdf, f"Segment: {loc.get('segment') or NOT_LOCALISED}")
    _p(pdf, f"OT layers: {layers}")
    if loc.get("note"):
        _p(pdf, f"Note: {loc['note']}")
    pdf.ln(1)
    _p(pdf, f"Status: {d.get('status')}" + (f" - {d['status_note']}" if d.get("status_note") else ""))
    pdf.ln(2)
    unc = d.get("uncertainty")
    if unc:
        _h(pdf, "Why Sensify is uncertain", 12)
        scores = {h.get("category"): h for h in d.get("hypotheses") or []}
        for c in unc.get("hypotheses") or []:
            h = scores.get(c) or {}
            _p(pdf, f"{CATEGORY_LABELS.get(c, c)}: score {round((h.get('score') or 0) * 100)} %, "
                    f"{len(h.get('evidence_ids') or [])} supporting evidence")
        if unc.get("discriminators"):
            _h(pdf, "What would tell them apart", 11)
            for x in unc["discriminators"]:
                _p(pdf, f"- {x}")
        pdf.ln(2)
    if d.get("timeline"):
        _h(pdf, "Timeline", 12)
        for t in d["timeline"]:
            _p(pdf, f"{_mmss(run, t.get('tick'))} | {t.get('kind')} | segment {t.get('segment') or NA} | "
                    f"{t.get('evidence_id')}")
            _p(pdf, f"{t.get('observation')} {t.get('interpretation')}")
        pdf.ln(2)
    if d.get("chain"):
        _h(pdf, "Attack-to-impact chain", 12)
        for st in d["chain"]:
            _p(pdf, f"{st.get('label')} | {_mmss(run, st.get('tick'))} | segment {st.get('segment') or NA}")
        pdf.ln(2)
    if d.get("mitre"):
        _h(pdf, "MITRE ATT&CK for ICS context (context, not attribution)", 12)
        for m in d["mitre"]:
            _p(pdf, f"{m.get('technique_id')} {m.get('name')} | {m.get('tactic')}")
            _p(pdf, f"Reason: {m.get('reason')}")
        pdf.ln(2)
    _h(pdf, "Evidence", 12)
    for e in d["evidence"]:
        _p(pdf, f"{e.get('id')} [{e.get('kind')}] {_mmss(run, e.get('tick'))}"
                f" segment {e.get('segment')}")
        _p(pdf, f"Observation: {e.get('observation')}")
        _p(pdf, f"Interpretation: {e.get('interpretation')}")
        pdf.ln(1)
    if d.get("actions"):
        _h(pdf, "Verification checks", 12)
        for a in d["actions"]:
            _p(pdf, f"- {a if isinstance(a, str) else a.get('text', a)}")
    return bytes(pdf.output())


def _sys_table(pdf, ds, systems: dict):
    _h(pdf, f"Systems A/B/C: {ds}", 12)
    names = list(systems)
    cols = {n: dict(system_criteria(systems[n])) for n in names}
    criteria = [c for c, _ in system_criteria(systems[names[0]])]
    w = [82] + [36] * len(names)
    pdf.set_font("DejaVu", "B", 9)
    for text, width in zip(["Criterion"] + [f"System {n}" for n in names], w):
        pdf.cell(width, 6, text, border=1)
    pdf.ln()
    pdf.set_font("DejaVu", "", 9)
    for c in criteria:
        name, kind = CRITERIA.get(c, (c, "pct"))
        pdf.cell(w[0], 6, name, border=1)
        for n, width in zip(names, w[1:]):
            pdf.cell(width, 6, fmt_metric(cols[n].get(c), kind), border=1)
        pdf.ln()
    pdf.ln(2)


def _target_line(key: str, c: dict) -> str:
    name, kind = TARGETS.get(key, (key, None))
    show = (lambda v: fmt_metric(v, kind)) if kind else fmt_value
    bound = "at least" if c["op"] == ">=" else "at most"
    return f"{name}: {show(c.get('value'))} (target {bound} {show(c['target'])}) {'Met' if c['passed'] else 'Missed'}"


def _start_block(pdf, height: float):
    if pdf.get_y() + height > pdf.page_break_trigger:
        pdf.add_page()


def _bar(pdf, x: float, y: float, value, fill: tuple[int, int, int], kind: str = "pct"):
    """A horizontal bar on a 0-100 % scale, 90 mm long at full scale, with its value after it."""
    if value is not None:
        pdf.set_fill_color(*fill)
        pdf.rect(x, y, max(0.3, 90 * min(1.0, value)), 3, style="F")
    pdf.set_xy(x + 92, y - 0.5)
    pdf.cell(30, 4, fmt_metric(value, kind))


def _charts(pdf, datasets: dict):
    """The evaluation page's charts: each criterion for each system, development and held-out side by side."""
    colours = {"development": (113, 105, 213), "heldout": (190, 186, 235)}
    names = [ds for ds in DATASET_TITLES if (datasets.get(ds) or {}).get("systems")]
    if not names:
        return
    values = {ds: {s: dict(system_criteria(doc)) for s, doc in datasets[ds]["systems"].items()} for ds in names}
    systems = list(values[names[0]])
    _start_block(pdf, 45)
    _h(pdf, "Charts", 12)
    _p(pdf, "Dark bars are " + " and light bars are ".join(DATASET_TITLES[ds].lower() for ds in names) + ".", 9)
    pdf.ln(1)
    for key in CHART_CRITERIA:
        _start_block(pdf, 7 + len(systems) * len(names) * 4)
        _h(pdf, CRITERIA[key][0], 10)
        pdf.set_font("DejaVu", "", 8)
        for s in systems:
            for i, ds in enumerate(names):
                y = pdf.get_y()
                if i == 0:
                    pdf.set_xy(pdf.l_margin, y - 0.5)
                    pdf.cell(20, 4, f"System {s}")
                na = key in CLASSIFICATION_ONLY and s != "C"
                _bar(pdf, pdf.l_margin + 22, y, None if na else _metric(values[ds][s].get(key)), colours[ds])
                pdf.set_xy(pdf.l_margin, y + 4)
        pdf.ln(1)
    pdf.ln(1)


def _metric(v):
    return v.get("rate") if isinstance(v, dict) else v


def _confusion(pdf, ds: str, conf: dict):
    rows = list(conf)
    cols = rows + sorted({c for r in rows for c in conf[r]} - set(rows))
    _start_block(pdf, 26 + 6 * len(rows))
    _h(pdf, f"Confusion matrix for C: {DATASET_TITLES.get(ds, ds)}", 12)
    _p(pdf, "Rows are the expected outcome, columns are what Sensify reported.", 9)
    w = [38] + [22] * len(cols)
    pdf.set_font("DejaVu", "B", 8)
    pdf.cell(w[0], 6, "Expected / reported", border=1)
    for c, width in zip(cols, w[1:]):
        pdf.cell(width, 6, CONFUSION_NAMES.get(c, c), border=1, align="C")
    pdf.ln()
    pdf.set_font("DejaVu", "", 8)
    for r in rows:
        pdf.cell(w[0], 6, CONFUSION_NAMES.get(r, r), border=1)
        for c, width in zip(cols, w[1:]):
            pdf.cell(width, 6, str(conf[r].get(c, 0)), border=1, align="C")
        pdf.ln()
    pdf.ln(3)


def evaluation_pdf(ev, results: dict) -> bytes:
    pdf = _pdf()
    _h(pdf, f"Evaluation e{ev.version}", 16)
    _p(pdf, f"Model v{results.get('model_version')} | engine {results.get('engine_version')} | "
            f"{results.get('created_at', '')}")
    pdf.ln(2)
    for ds, doc in results.get("datasets", {}).items():
        if doc.get("systems"):
            _sys_table(pdf, ds, doc["systems"])
    for ds, checks in results.get("targets_check", {}).items():
        _h(pdf, f"Targets: {ds}", 12)
        for name, c in checks.items():
            _p(pdf, _target_line(name, c))
        pdf.ln(1)
    _charts(pdf, results.get("datasets", {}))
    shown = False
    for ds, doc in results.get("datasets", {}).items():
        conf = (((doc.get("systems") or {}).get("C") or {}).get("investigation") or {}).get("confusion")
        if conf:
            _confusion(pdf, ds, conf)
            shown = True
    if shown:
        _p(pdf, "Reporting = " + CATEGORY_LABELS["reporting_inconsistency"] + ".", 9)
    return bytes(pdf.output())
