import csv
import io
from datetime import timedelta


def _render(header: list[str], rows: list[list]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue()


def incident_time(run, tick: int) -> str:
    return (run.started_at + timedelta(seconds=tick * run.tick_seconds)).isoformat()


def confidence_text(d: dict) -> str:
    """'44 % Low', as the incident page shows it."""
    c = d.get("confidence")
    return f"{round(c * 100)} % {d.get('confidence_label')}" if c is not None else str(d.get("confidence_label"))


def incident_csv(d: dict, run, label: str | None = None) -> str:
    """One row per displayed item; the section column says what each row holds."""
    loc = d.get("localisation") or {}
    unc = d.get("uncertainty") or {}

    def at(tick) -> str:
        return incident_time(run, tick or 0)

    fields = [("key", d.get("key")), ("classification", label or d.get("classification")),
              ("confidence", confidence_text(d)), ("severity", d.get("severity")), ("status", d.get("status")),
              ("status_note", d.get("status_note")), ("segment", loc.get("segment") or "Not localised"),
              ("ot_layers", "; ".join(loc.get("ot_layers") or [])), ("location_note", loc.get("note")),
              ("summary", d.get("summary"))]
    rows = [["incident", "", name, "", "", "", value, ""] for name, value in fields]
    rows += [["hypothesis", h.get("category"), "score", "", "", "", h.get("score"), "; ".join(h.get("evidence_ids") or [])]
             for h in d.get("hypotheses") or []]
    rows += [["discriminator", "", "", "", "", "", x, ""] for x in unc.get("discriminators") or []]
    rows += [["timeline", t.get("evidence_id"), t.get("kind"), t.get("tick"), at(t.get("tick")), t.get("segment"),
              t.get("observation"), t.get("interpretation")] for t in d.get("timeline") or []]
    rows += [["chain", s.get("stage"), s.get("label"), s.get("tick"), at(s.get("tick")), s.get("segment"),
              "; ".join(s.get("evidence_ids") or []), ""] for s in d.get("chain") or []]
    rows += [["mitre", m.get("technique_id"), m.get("name"), "", "", "", m.get("tactic"), m.get("reason")]
             for m in d.get("mitre") or []]
    rows += [["evidence", e.get("id"), e.get("kind"), e.get("tick"), at(e.get("tick")), e.get("segment"),
              e.get("observation"), e.get("interpretation")] for e in d["evidence"]]
    rows += [["check", "", "", "", "", "", a, ""] for a in d.get("actions") or []]
    return _render(["section", "id", "kind", "tick", "time", "segment", "observation", "interpretation"], rows)


NA = "not available"

DETECTION_CRITERIA = [
    ("detection_rate", ("overall",)),
    ("detection_rate_per_type_min", ("per_type_min_rate",)),
    ("tick_false_alarm_rate", ("false_alarm", "tick_rate")),
    ("false_windows_per_run", ("false_alarm", "windows_per_run")),
    ("window_precision", ("window_precision",)),
    ("time_to_detect_median_s", ("time_to_detect_s", "median")),
    ("localization_hit_rate", ("localization_hit_rate",)),
]
INVESTIGATION_CRITERIA = ["incident_detection", "classification_accuracy", "decision_coverage",
                          "ambiguity_handled", "segment_localisation", "ot_layer_accuracy",
                          "incidents_per_normal_run", "unexplained_per_normal_run", "incidents_outside_event"]


def _rate(v):
    return v.get("rate") if isinstance(v, dict) else v


def _num(v):
    return NA if v is None else v


def _get(d, *path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def system_criteria(sysdoc: dict) -> list[tuple[str, object]]:
    """Ordered (criterion, value) pairs for one system; None means not available."""
    det = sysdoc.get("detection") or {}
    inv = sysdoc.get("investigation") or {}
    out = [(name, _rate(_get(det, *path))) for name, path in DETECTION_CRITERIA]
    out += [(name, _rate(inv.get(name))) for name in INVESTIGATION_CRITERIA]
    return out


def evaluation_rows(results: dict) -> list[list]:
    """dataset, system, criterion, value, target, met. Per-run rows appear only when results still hold them."""
    rows = []
    for ds, doc in results.get("datasets", {}).items():
        for sysname, sysdoc in doc.get("systems", {}).items():
            for name, v in system_criteria(sysdoc):
                rows.append([ds, sysname, name, _num(v), "", ""])
            for t, v in ((sysdoc.get("detection") or {}).get("per_type") or {}).items():
                rows.append([ds, sysname, f"detection_rate:{t}", _num(_rate(v)), "", ""])
            for expected, row in ((sysdoc.get("investigation") or {}).get("confusion") or {}).items():
                for reported, n in row.items():
                    rows.append([ds, sysname, f"confusion:{expected}->{reported}", n, "", ""])
    for ds, checks in results.get("targets_check", {}).items():
        for name, c in checks.items():
            rows.append([ds, "", name, _num(_rate(c.get("value"))), f'{c["op"]} {c["target"]}',
                         "yes" if c["passed"] else "no"])
    for r in results.get("per_run", []) or []:
        rows.append(["per_run", "", str(r.get("run_id", "")), "", "", ""])
    return rows


def evaluation_csv(results: dict) -> str:
    return _render(["dataset", "system", "criterion", "value", "target", "met"], evaluation_rows(results))
