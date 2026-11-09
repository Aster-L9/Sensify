from dataclasses import dataclass

ENGINE_VERSION = "i2"


@dataclass(frozen=True)
class EngineConfig:
    gap_ticks: int = 36
    event_lookback_ticks: int = 60
    setpoint_tol_pct: float = 5.0
    setpoint_min_ticks: int = 6
    setpoint_settle_ticks: int = 6
    min_score: float = 0.35
    margin: float = 0.15
    response_window_ticks: int = 24


DEFAULT_CONFIG = EngineConfig()
