import numpy as np

from app.analysis.frame import ObservableEvent, ReportedRun
from app.analysis.windows import AlertRecord
from app.investigation.config import DEFAULT_CONFIG as CFG
from app.investigation.grouping import group, group_flags
from app.investigation.signals import is_opening_event, setpoint_departures
from tests.helpers import rep


def ev(tick=10, category="control", authorized="yes", etype="Valve command issued", details=""):
    return ObservableEvent(tick, "SEG-05", "Control Layer", category, etype, authorized, "low", details)


def empty_run(T=300, events=()):
    nan = np.full((T, 6), np.nan)
    z = np.zeros((T, 6))
    return ReportedRun(z.copy(), z.copy(), z.copy(), nan.copy(), nan.copy(), list(events))


def alert(s, e, seg=1):
    return AlertRecord(seg, s, e, s, 0.8, 0.9, [], "medium", "")


def test_opening_events():
    assert is_opening_event(ev(authorized="no"))
    assert is_opening_event(ev(category="security", authorized="unknown"))
    assert not is_opening_event(ev(authorized="yes"))


def test_unauthorized_valve_close_is_a_departure():
    run = rep(scenario_type="unauthorized_control", method="valve_close", target_segment="SEG-05",
              magnitude=0.9, onset_min=2, seed=5)
    deps = [d for d in setpoint_departures(run, CFG) if d.segment == "SEG-05"]
    assert deps and 24 <= deps[0].start_tick <= 36


def test_authorized_operator_change_is_not_a_departure():
    for s in range(300, 331):
        run = rep(scenario_type="normal", seed=s)
        if any(e.authorized == "yes" and e.event_type in ("Valve command issued", "Pump command issued")
               for e in run.events):
            assert setpoint_departures(run, CFG) == []
            return
    raise AssertionError("no seed with an authorized command")


def test_windows_within_gap_merge():
    state = np.full((300, 6), "normal", dtype=object)
    run = empty_run()
    assert len(group(run, [alert(10, 20), alert(50, 60)], state, CFG)) == 1
    assert len(group(run, [alert(10, 20), alert(100, 110)], state, CFG)) == 2


def test_event_opens_span_without_alerts():
    state = np.full((300, 6), "normal", dtype=object)
    run = empty_run(events=[ev(tick=77, authorized="no")])
    spans = group(run, [], state, CFG)
    assert len(spans) == 1 and spans[0].start == 77 and spans[0].opening_events == [0]


def test_group_flags_matches_a_b_semantics():
    flags = np.zeros((100, 3), dtype=bool)
    flags[10:20, 0] = True
    flags[15:30, 1] = True
    assert group_flags(flags, CFG) == [(10, 29)]
