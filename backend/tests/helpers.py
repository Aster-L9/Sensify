"""Test helpers shared across test modules."""


def launch(client, headers, **kw):
    body = {"scenario_type": "unauthorized_control", "method": "valve_close", "target_segment": "SEG-05",
            "seed": 5, "playback_speed": 10} | kw
    return client.post("/scenarios", json=body, headers=headers)


def wait_until(fn, timeout=120.0, interval=0.2):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if fn():
            return True
        time.sleep(interval)
    raise TimeoutError("condition not met in time")


def reported_from_rundata(data):
    """What the analysis may see of a simulated run: reported values and observable events only."""
    from app.analysis.frame import ObservableEvent, ReportedRun

    events = [ObservableEvent(e.tick, e.segment, e.source, e.category, e.event_type, e.authorized, e.severity)
              for e in data.events if e.observable]
    return ReportedRun(
        pressure=data.reported["pressure"].copy(), flow=data.reported["flow"].copy(),
        temperature=data.reported["temperature"].copy(), valve_open=data.reported["valve_open"].copy(),
        pump_speed=data.reported["pump_speed"].copy(), events=events,
    )


def rep(**cfg):
    from app.sim.engine import simulate_run
    from app.sim.scenarios import validate_config

    cfg.setdefault("seed", 1)
    return reported_from_rundata(simulate_run(validate_config(cfg)))


def normal_runs(n, start_seed):
    return [rep(scenario_type="normal", seed=start_seed + i) for i in range(n)]
