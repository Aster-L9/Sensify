"""Presentation layer: summary, timeline, attack-to-impact chain, MITRE ATT&CK for ICS context, checks, severity."""
from app.investigation.evidence import Facts
from app.investigation.types import (CATEGORY_LABELS, UNCERTAIN, ChainStage, EvidenceItem, Hypothesis, Localisation,
                                     Technique, TimelineEntry)

NO_CONTROL_LINE = "Sensify never issues control commands; these are checks for people to carry out."
_SEV_RANK = {"medium": 0, "high": 1, "critical": 2}


def fmt_tick(t: int) -> str:
    s = int(t) * 5
    return f"T+{s // 60:02d}:{s % 60:02d}"


def _equip(ev) -> str:
    et = getattr(ev, "event_type", "").lower()
    if "valve" in et:
        return "valve V-12"
    if "pump" in et:
        return "pump P-3"
    return "equipment"


def _join(items: list[str]) -> str:
    """'A', 'A and B', 'A, B and C'."""
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} and {items[-1]}"


def _nm(c: str) -> str:
    return CATEGORY_LABELS.get(c, c).lower()


def summary(category: str, f: Facts, loc: Localisation, hypotheses: list[Hypothesis]) -> str:
    seg = loc.segment
    at = f" at {seg}" if seg else ""
    if category == UNCERTAIN:
        if len(hypotheses) >= 2:
            return f"The evidence fits both {_nm(hypotheses[0].category)} and {_nm(hypotheses[1].category)} about equally."
        return "The evidence does not point clearly to one explanation."
    if category == "cyber_manipulation":
        if f.unauth_cmds:
            c = f.unauth_cmds[0]
            others = sorted((f.honest_change_segs | f.flagged_segs) - {c.segment})
            if others:
                tail = f" was followed by changes at {_join([c.segment] + others[:3])}"
                if not f.contradicted_segs:
                    tail += " while their readings stayed consistent"
            else:
                tail = f" was followed by changes at {c.segment}"
            return f"An unauthorized {_equip(c)} command at {c.segment} at {fmt_tick(c.tick)}{tail}."
        if f.replay_segs:
            r = sorted(f.replay_segs)[0]
            return f"Readings at {r} repeated an earlier pattern, which is consistent with replayed reporting."
        if f.reporting_change_segs:
            return f"A reporting configuration change{at} coincides with readings that disagree with neighbouring segments."
        if f.departures:
            d = f.departures[0]
            return (f"Reported {d.equipment} position at {d.segment} departed from its last authorized command "
                    f"at {fmt_tick(d.start_tick)}.")
        return "The evidence is consistent with possible cyber manipulation."
    if category == "reporting_inconsistency":
        return (f"Readings{at} disagree with neighbouring segments that show a real change, "
                "which is consistent with a reporting inconsistency.")
    if category == "sensor_fault":
        return f"Readings{at} show a single-segment fault pattern that is consistent with a sensor or device fault."
    if category == "physical_anomaly":
        near = f" around {seg}" if seg else ""
        return f"Neighbouring segments{near} show a supported change that is consistent with a physical or process anomaly."
    return f"Activity{at} coincides with an authorized operator command and is consistent with normal behaviour."


def timeline(evidence: list[EvidenceItem]) -> list[TimelineEntry]:
    return [TimelineEntry(e.tick, e.segment, e.kind, e.observation, e.interpretation, e.id)
            for e in sorted(evidence, key=lambda e: (e.tick, e.id))]


def _first(evidence, pred):
    return next((e for e in sorted(evidence, key=lambda e: e.tick) if pred(e)), None)


def _is_replay(e) -> bool:
    return e.kind == "consistency check" and "replay" in e.interpretation.lower()


def chain(category: str, f: Facts, evidence: list[EvidenceItem]) -> list[ChainStage]:
    if category not in ("cyber_manipulation", "reporting_inconsistency"):
        return []
    access = _first(evidence, lambda e: "unregistered workstation" in e.observation.lower()) if f.security_ws else None
    action = (_first(evidence, lambda e: e.link.get("type") == "event" and e.supports.get("cyber_manipulation", 0) >= 0.5
                     and "command" in e.observation.lower())
              or _first(evidence, lambda e: "Reporting configuration change" in e.observation)
              or _first(evidence, _is_replay))
    if action is None:
        action_label = "Command or reporting change"
    elif _is_replay(action):
        action_label = "Readings replayed from an earlier period"
    elif "Reporting configuration change" in action.observation:
        action_label = "Reporting configuration changed"
    else:
        action_label = f"Unauthorized {_equip(next(iter(f.unauth_cmds), None))} command" if f.unauth_cmds else "Unauthorized command"
    equipment = _first(evidence, lambda e: e.kind in ("equipment state", "setpoint departure"))
    equipment_label = ("Position moved away from the authorized setting" if equipment is not None
                       and equipment.kind == "setpoint departure" else "Equipment state changed")
    process = _first(evidence, lambda e: e.kind == "telemetry anomaly")
    cands = [
        ("access", "Access from an unregistered workstation", access),
        ("action", action_label, action),
        ("equipment", equipment_label, equipment),
        ("process", f"Process change at {process.segment}" if process is not None and process.segment else "Process change", process),
        ("visibility", "Reported readings contradicted",
         _first(evidence, lambda e: e.kind == "trust drop" or _is_replay(e))),
        ("detection", "First Sensify alert", _first(evidence, lambda e: e.kind in ("telemetry anomaly", "trust drop"))),
    ]
    out = [ChainStage(k, lab, e.tick, e.segment, [e.id]) for k, lab, e in cands if e is not None]
    # One item can fill two stages (process and detection), so count the evidence rather than the stages.
    return out if len({i for st in out for i in st.evidence_ids}) >= 2 else []


def mitre(category: str, f: Facts, evidence: list[EvidenceItem]) -> list[Technique]:
    if category not in ("cyber_manipulation", "reporting_inconsistency"):
        return []

    def ids(pred):
        return [e.id for e in evidence if pred(e)]

    out: list[Technique] = []
    if f.security_ws:
        out.append(Technique("T0848", "Rogue Master", "Initial Access",
                             "A command came from an unregistered workstation.",
                             ids(lambda e: "unregistered workstation" in e.observation.lower())))
    if f.unauth_cmds:
        out.append(Technique("T0855", "Unauthorized Command Message", "Impair Process Control",
                             "An unauthorized command appears in the event log.",
                             ids(lambda e: e.link.get("type") == "event" and "command" in e.observation.lower()
                                 and e.supports.get("cyber_manipulation", 0) >= 0.5)))
    if f.unauth_state or f.departures:
        eq = ids(lambda e: e.kind in ("equipment state", "setpoint departure"))
        out.append(Technique("T0836", "Modify Parameter", "Impair Process Control",
                             "Equipment state or position differs from the last authorized command.", eq))
        out.append(Technique("T0831", "Manipulation of Control", "Impact",
                             "Equipment operation differs from what was commanded.", eq))
        out.append(Technique("T0828", "Loss of Productivity and Revenue", "Impact",
                             "Changed equipment operation coincides with altered process readings.",
                             ids(lambda e: e.kind == "telemetry anomaly")))
    if f.replay_segs or (f.reporting_change_segs & f.contradicted_segs):
        rep_ev = ids(lambda e: _is_replay(e) or "Reporting configuration change" in e.observation)
        out.append(Technique("T0856", "Spoof Reporting Message", "Evasion",
                             "Reported readings repeat or disagree with neighbours.", rep_ev))
        out.append(Technique("T0832", "Manipulation of View", "Impact",
                             "The operators' view of the process may differ from the process.", rep_ev))
    if category == "reporting_inconsistency":
        out.append(Technique("T0829", "Loss of View", "Impact",
                             "Readings at a segment are not supported by neighbours.",
                             ids(lambda e: e.kind == "trust drop")))
    seen, res = set(), []
    for t in out:
        if t.technique_id not in seen:
            seen.add(t.technique_id)
            res.append(t)
    return res


_ACTIONS = {
    "cyber_manipulation": [
        "Check the access log for the {seg} control system around the time of the command, "
        "because an unexplained login would show how the command was sent.",
        "Confirm with field staff the physical position of the {eq} at {seg}, "
        "because the reported position may differ from what is happening on site.",
        "Compare the {eq} position reported by the control system with the commanded position, "
        "because a difference shows whether the command took effect.",
        "Review whether the workstation that sent the command is registered, "
        "because a command from an unregistered workstation points to unauthorized access.",
    ],
    "reporting_inconsistency": [
        "Check the reporting configuration at {seg} against its approved settings, "
        "because an unapproved setting could explain why the readings disagree.",
        "Compare {seg} readings with a local gauge or neighbouring segments, "
        "because they show what the process is actually doing.",
        "Review recent reporting configuration changes for {seg}, "
        "because a recent change could mark when the readings stopped being reliable.",
    ],
    "sensor_fault": [
        "Inspect the sensor and transmitter at {seg} on site, "
        "because the pattern is limited to one segment and points to the device.",
        "Compare {seg} readings with a handheld reference instrument, "
        "because agreement would rule out a faulty reading.",
        "Review the device diagnostics for {seg}, because a device fault would normally show there.",
    ],
    "physical_anomaly": [
        "Inspect the pipe and equipment around {seg} for leaks or blockages, "
        "because supported changes across segments point to a real process change.",
        "Compare flow and pressure readings between {seg} and adjacent segments, "
        "because the pattern between them helps show where the change began.",
        "Confirm that no maintenance work was under way near {seg}, because planned work could explain the change.",
    ],
    "normal_behaviour": [
        "Confirm the authorized command near {seg} matches the work order, "
        "because a match supports treating this activity as normal.",
        "Check that readings at {seg} returned to the usual range afterwards, "
        "because a lasting change would need a closer look.",
    ],
}
# Cyber incidents with no unauthorized command (replay, reporting change, setpoint departure) have no command to check.
_CYBER_NO_COMMAND = [
    "Check the reporting configuration at {seg} against its approved settings, "
    "because an unapproved change could explain readings that repeat or disagree.",
    "Compare {seg} readings with a local gauge at the same time, "
    "because a difference shows the reported values are not the live process.",
    "Review the access log for the {seg} reporting system, "
    "because an unexplained login would point to manipulation rather than a fault.",
]
_DEPARTURE_CHECK = ("Confirm with field staff the physical position of the {eq} at {seg}, "
                    "because the reported position departed from its last authorized command.")


def _checks(category: str, f: Facts) -> list[str]:
    if category != "cyber_manipulation":
        return _ACTIONS.get(category, _ACTIONS["normal_behaviour"])
    if f.unauth_cmds:
        return _ACTIONS["cyber_manipulation"]
    return _CYBER_NO_COMMAND + ([_DEPARTURE_CHECK] if f.departures else [])


def actions(category: str, loc: Localisation, f: Facts, hypotheses: list[Hypothesis] | None = None) -> list[str]:
    seg = loc.segment or "the affected segment"
    eq = "equipment"
    if f.unauth_cmds:
        eq = _equip(f.unauth_cmds[0])
    elif f.departures:
        eq = f.departures[0].equipment
    if category == UNCERTAIN:
        lines = [_checks(h.category, f)[0].format(seg=seg, eq=eq) for h in (hypotheses or [])[:2] if h.category in _ACTIONS]
        if not lines:
            lines = [f"Inspect {seg} on site and compare its readings with neighbouring segments."]
    else:
        lines = [a.format(seg=seg, eq=eq) for a in _checks(category, f)][:4]
    return lines + [NO_CONTROL_LINE]


_DISCRIMINATORS = {
    ("cyber_manipulation", "physical_anomaly"): ["Whether the command source is a registered workstation",
                                                 "Whether the equipment position matches the last authorized command"],
    ("reporting_inconsistency", "sensor_fault"): ["Whether neighbouring segments show a real change",
                                                  "Whether a local gauge agrees with the reported reading"],
    ("physical_anomaly", "sensor_fault"): ["Whether neighbouring segments show a matching change",
                                           "Whether a handheld instrument agrees with the reading"],
    ("cyber_manipulation", "reporting_inconsistency"): ["Whether a reporting configuration change was logged",
                                                        "Whether the field reading differs from the reported one"],
    ("normal_behaviour", "physical_anomaly"): ["Whether an authorized command or work order explains the change",
                                               "Whether readings returned to the usual range"],
}


def uncertainty(hypotheses: list[Hypothesis]) -> dict | None:
    if len(hypotheses) < 2:
        return None
    a, b = hypotheses[0].category, hypotheses[1].category
    disc = _DISCRIMINATORS.get(tuple(sorted((a, b)))) or [
        "Whether on-site observations match the reported readings",
        "Whether neighbouring segments show the same change"]
    return {"hypotheses": [a, b], "discriminators": list(disc)}


def _norm_sev(s: str) -> str:
    return s if s in ("high", "critical") else "medium"


def severity(windows, category: str, f: Facts, events=None) -> str:
    if category == "cyber_manipulation" and (f.unauth_state or f.departures):
        return "critical"
    sevs = [_norm_sev(w.severity) for w in windows]
    if not sevs:
        sevs = [_norm_sev(e.severity) for e in (events or [])]
    if not sevs:
        return "medium"
    return max(sevs, key=lambda s: _SEV_RANK[s])
