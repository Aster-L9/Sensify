import pytest

from app.sim.scenarios import (
    CATALOG, SCENARIO_TYPES, ScenarioError, envelope, validate_config,
)


def test_defaults_and_ticks():
    c = validate_config({"scenario_type": "physical_anomaly", "target_segment": "SEG-04", "seed": 7})
    assert (c.method, c.onset_tick, c.ramp_ticks, c.active_ticks, c.recovery_ticks, c.duration_ticks) == ("leak", 72, 12, 72, 24, 240)


@pytest.mark.parametrize("raw", [
    {"scenario_type": "unauthorized_control", "method": "valve_close", "target_segment": "SEG-02"},
    {"scenario_type": "telemetry_manipulation", "method": "replay", "target_segment": "SEG-04"},
    {"scenario_type": "physical_anomaly", "target_segment": "SEG-04", "magnitude": 1.5},
    {"scenario_type": "physical_anomaly", "target_segment": "SEG-04", "onset_min": 15, "active_min": 6},
    {"scenario_type": "sensor_fault", "target_segment": "SEG-01", "playback_speed": 7},
    {"scenario_type": "bogus"},
])
def test_invalid_configs_rejected(raw):
    with pytest.raises(ScenarioError):
        validate_config(raw)


def test_envelope_shape():
    e = envelope(validate_config({"scenario_type": "physical_anomaly", "target_segment": "SEG-04", "seed": 1}))
    assert e[71] == 0 and e[84] == 1 and e[155] == 1 and e[180] == 0 and e.max() == 1


def test_envelope_without_recovery_holds_to_end():
    c = validate_config({"scenario_type": "physical_anomaly", "target_segment": "SEG-04", "recovery": False, "seed": 1})
    e = envelope(c)
    assert e[-1] == 1 and c.event_end_tick == c.duration_ticks - 1


def test_catalog_lists_all_types_with_targets():
    ids = [t["id"] for t in CATALOG]
    assert ids == list(SCENARIO_TYPES)
    uc = next(t for t in CATALOG if t["id"] == "unauthorized_control")
    assert {m["id"]: m["allowed_targets"] for m in uc["methods"]}["valve_close"] == ["SEG-05"]


def test_seed_must_fit_a_database_integer():
    assert validate_config({"scenario_type": "normal", "seed": 2**31 - 1}).seed == 2**31 - 1
    with pytest.raises(ScenarioError, match="seed"):
        validate_config({"scenario_type": "normal", "seed": 2**63})
