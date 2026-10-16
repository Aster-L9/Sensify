"""
Scenario catalog, launch-parameter validation and the effect envelope.
"""
import secrets
from dataclasses import asdict, dataclass

import numpy as np

from app.sim.topology import SEGMENT_CODES, TICK_SECONDS

TICKS_PER_MIN = 60 // TICK_SECONDS
RECOVERY_MIN = 2
PLAYBACK_SPEEDS = (1, 5, 10, 20)
MAX_SEED = 2**31 - 1  # stored in an SQLite INTEGER column; generated seeds stay below 10**6

SCENARIO_TYPES = (
    "normal",
    "physical_anomaly",
    "sensor_fault",
    "telemetry_manipulation",
    "unauthorized_control",
    "concealed_physical_incident",
)

EXPECTED_ROOT_CAUSE = {
    "normal": "Normal Behavior",
    "physical_anomaly": "Physical/Process Anomaly",
    "sensor_fault": "Sensor/Device Fault",
    "telemetry_manipulation": "Possible Cyber Manipulation",
    "unauthorized_control": "Possible Cyber Manipulation",
    "concealed_physical_incident": "Physical/Process Anomaly + reporting inconsistency",
}

_ALL = list(SEGMENT_CODES)
_EQUIPPED = ["SEG-01", "SEG-03", "SEG-05", "SEG-06"]


def _method(id, label, description, targets):
    return {"id": id, "label": label, "description": description, "allowed_targets": list(targets)}


CATALOG: list[dict] = [
    {
        "id": "normal", "label": "Normal Operation", "cyber": False, "magnitude_label": None,
        "description": "Baseline behaviour: natural demand drift plus routine authorized operator adjustments.",
        "methods": [],
    },
    {
        "id": "physical_anomaly", "label": "Physical Anomaly", "cyber": False,
        "magnitude_label": "Leak size / restriction",
        "description": "A real process problem at the target, reported honestly.",
        "methods": [
            _method("leak", "Leak", "Product escapes mid-segment; flow and pressure fall downstream.", _ALL),
            _method("blockage", "Blockage", "A partial restriction raises the segment's resistance; flow falls along the line.", _ALL),
        ],
    },
    {
        "id": "sensor_fault", "label": "Sensor / Device Fault", "cyber": False,
        "magnitude_label": "Fault amplitude",
        "description": "The target's instrument misreports while the process stays unchanged.",
        "methods": [
            _method("erratic", "Erratic", "Reported values jump around the true value.", _ALL),
            _method("stuck", "Stuck", "The reported value freezes at its last good reading.", _ALL),
            _method("drift", "Drift", "A bias grows steadily on the reported value.", _ALL),
        ],
    },
    {
        "id": "telemetry_manipulation", "label": "Telemetry Manipulation", "cyber": True,
        "magnitude_label": "Hidden change / false offset",
        "description": "An attacker alters what the target reports.",
        "methods": [
            _method("replay", "Replay", "Recorded normal readings are replayed while the process is covertly changed at the target's equipment.", _EQUIPPED),
            _method("bias", "False offset", "A false offset is added to the target's reported pressure.", _ALL),
        ],
    },
    {
        "id": "unauthorized_control", "label": "Unauthorized Control", "cyber": True,
        "magnitude_label": "Control change",
        "description": "Unauthorized commands drive equipment away from its setpoint; readings stay honest.",
        "methods": [
            _method("valve_close", "Valve closure", "Valve V-12 is stepped toward closed.", ["SEG-05"]),
            _method("pump_slowdown", "Pump slowdown", "Pump speed is reduced.", ["SEG-03"]),
            _method("pump_stop", "Pump stop", "The pump is tripped.", ["SEG-03"]),
        ],
    },
    {
        "id": "concealed_physical_incident", "label": "Concealed Physical Incident", "cyber": True,
        "magnitude_label": "Leak size",
        "description": "A real leak while the target's reported values are held at normal-looking levels.",
        "methods": [
            _method("leak", "Concealed leak", "A real leak with the target's readings held near normal.", _ALL),
        ],
    },
]

_BY_ID = {t["id"]: t for t in CATALOG}


class ScenarioError(ValueError):
    pass


@dataclass(frozen=True)
class ScenarioConfig:
    scenario_type: str
    method: str | None
    target_segment: str | None
    magnitude: float
    variable: str
    onset_min: float
    ramp_min: float
    active_min: float
    recovery: bool
    duration_min: float
    playback_speed: int
    seed: int

    @property
    def onset_tick(self) -> int:
        return round(self.onset_min * TICKS_PER_MIN)

    @property
    def ramp_ticks(self) -> int:
        return round(self.ramp_min * TICKS_PER_MIN)

    @property
    def active_ticks(self) -> int:
        return round(self.active_min * TICKS_PER_MIN)

    @property
    def recovery_ticks(self) -> int:
        return RECOVERY_MIN * TICKS_PER_MIN if self.recovery else 0

    @property
    def duration_ticks(self) -> int:
        return round(self.duration_min * TICKS_PER_MIN)

    @property
    def event_end_tick(self) -> int:
        """Last tick with an effect; without recovery the effect holds to the end of the run."""
        if not self.recovery:
            return self.duration_ticks - 1
        end = self.onset_tick + self.ramp_ticks + self.active_ticks + self.recovery_ticks
        return min(end, self.duration_ticks - 1)

    def to_params(self) -> dict:
        return asdict(self)


def _number(raw: dict, key: str, default: float, lo: float, hi: float) -> float:
    value = raw.get(key)
    if value is None:
        value = default
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ScenarioError(f"{key} must be a number")
    if not lo <= value <= hi:
        raise ScenarioError(f"{key} must be between {lo:g} and {hi:g}")
    return value


def validate_config(raw: dict) -> ScenarioConfig:
    scenario_type = raw.get("scenario_type")
    if scenario_type not in _BY_ID:
        raise ScenarioError(f"Unknown scenario type: {scenario_type!r}")
    spec = _BY_ID[scenario_type]

    method, target = None, None
    if spec["methods"]:
        methods = {m["id"]: m for m in spec["methods"]}
        method = raw.get("method") or spec["methods"][0]["id"]
        if method not in methods:
            raise ScenarioError(f"Unknown method {method!r} for {spec['label']}")
        target = raw.get("target_segment")
        allowed = methods[method]["allowed_targets"]
        if target not in allowed:
            raise ScenarioError(
                f"{target or 'No segment'} is not a valid target for {methods[method]['label']} "
                f"(allowed: {', '.join(allowed)})"
            )

    variable = raw.get("variable") or "pressure"
    if scenario_type == "sensor_fault":
        if variable not in ("pressure", "flow"):
            raise ScenarioError("variable must be 'pressure' or 'flow'")
    else:
        variable = "pressure"

    magnitude = _number(raw, "magnitude", 0.6, 0.1, 1.0)
    onset_min = _number(raw, "onset_min", 6, 1, 28)
    ramp_min = _number(raw, "ramp_min", 1, 0.5, 5)
    active_min = _number(raw, "active_min", 6, 1, 25)
    duration_min = _number(raw, "duration_min", 20, 10, 30)
    recovery = bool(raw.get("recovery", True))
    has_event = bool(spec["methods"])  # a normal run has no event, so its timing never constrains the length
    if has_event and onset_min + ramp_min + active_min + (RECOVERY_MIN if recovery else 0) > duration_min - 1:
        raise ScenarioError("The scenario timing does not fit in the run length")

    playback_speed = raw.get("playback_speed", 10)
    if playback_speed not in PLAYBACK_SPEEDS:
        raise ScenarioError(f"playback_speed must be one of {', '.join(map(str, PLAYBACK_SPEEDS))}")

    seed = raw.get("seed")
    if seed is None:
        seed = secrets.randbelow(10 ** 6)
    if not isinstance(seed, int) or isinstance(seed, bool) or not 0 <= seed <= MAX_SEED:
        raise ScenarioError(f"seed must be a whole number from 0 to {MAX_SEED}")

    return ScenarioConfig(
        scenario_type=scenario_type, method=method, target_segment=target,
        magnitude=magnitude, variable=variable, onset_min=onset_min, ramp_min=ramp_min,
        active_min=active_min, recovery=recovery, duration_min=duration_min,
        playback_speed=playback_speed, seed=seed,
    )


def envelope(cfg: ScenarioConfig) -> np.ndarray:
    """Effect strength 0..1 per tick: ramp up, hold while active, ramp down on recovery."""
    e = np.zeros(cfg.duration_ticks)
    if cfg.scenario_type == "normal":
        return e
    t = np.arange(cfg.duration_ticks)
    on, ramp = cfg.onset_tick, max(cfg.ramp_ticks, 1)
    hold_end = on + ramp + cfg.active_ticks
    e = np.where((t >= on) & (t < on + ramp), (t - on + 1) / ramp, e)
    e = np.where((t >= on + ramp) & (t < hold_end), 1.0, e)
    if cfg.recovery:
        rec = cfg.recovery_ticks
        e = np.where((t >= hold_end) & (t < hold_end + rec), 1 - (t - hold_end + 1) / rec, e)
    else:
        e = np.where(t >= hold_end, 1.0, e)
    return e
