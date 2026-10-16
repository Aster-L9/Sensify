from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


# ── Auth Schemas ───────────────────────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ── User Schemas ───────────────────────────────────────────────────────────────
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None


class UserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserCreateAdmin(BaseModel):
    username: str
    email: str
    password: str
    role: str = "analyst"


# ── Segment Schemas ────────────────────────────────────────────────────────────
class SegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    segment_type: str
    order_index: int
    lat_start: float
    lon_start: float
    lat_end: float
    lon_end: float
    length_km: float
    diameter_mm: float
    design_pressure_bar: float
    equipment: Optional[str] = None


class TopologyResponse(BaseModel):
    segments: List[SegmentResponse]
    total_length_km: float
    segment_count: int


# ── Scenario / Run Schemas ─────────────────────────────────────────────────────
class ScenarioLaunch(BaseModel):
    scenario_type: str
    method: Optional[str] = None
    target_segment: Optional[str] = None
    magnitude: Optional[float] = None
    variable: Optional[str] = None
    onset_min: Optional[float] = None
    ramp_min: Optional[float] = None
    active_min: Optional[float] = None
    recovery: Optional[bool] = None
    duration_min: Optional[float] = None
    playback_speed: Optional[int] = None
    seed: Optional[int] = None
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class RunCreate(BaseModel):
    """Launch a normal-operation run (the dashboard's quick launch)."""
    name: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    seed: Optional[int] = None
    playback_speed: Optional[int] = None
    duration_min: Optional[float] = None


# ── Telemetry / State / Event Schemas ──────────────────────────────────────────
class TelemetryPoint(BaseModel):
    run_id: int
    segment_id: int
    segment_code: str
    tick: int
    timestamp: datetime
    pressure_bar: float
    flow_m3h: float
    temperature_c: float
    valve_open_pct: Optional[float] = None
    pump_speed_pct: Optional[float] = None
    valve_state: Optional[str] = None
    equipment_state: Optional[str] = None


class SegmentStateOut(BaseModel):
    segment_id: int
    code: str
    name: str
    segment_type: str
    pressure_bar: Optional[float] = None
    flow_m3h: Optional[float] = None
    temperature_c: Optional[float] = None
    valve_open_pct: Optional[float] = None
    pump_speed_pct: Optional[float] = None
    valve_state: Optional[str] = None
    equipment_state: Optional[str] = None
    anomaly_score: Optional[float] = None
    ml_flag: bool = False
    trust_score: Optional[float] = None
    trust_status: Optional[str] = None
    state: str = "normal"
    top_factor: Optional[dict] = None
    factors: List[dict] = []


class RunStateOut(BaseModel):
    run_id: int
    status: str
    tick: int
    revealed_ticks: int
    duration_ticks: int
    timestamp: datetime
    segments: List[SegmentStateOut]
    open_alerts: int = 0


class EventOut(BaseModel):
    id: int
    run_id: int
    tick: int
    timestamp: datetime
    segment_id: Optional[int] = None
    segment_code: Optional[str] = None
    source: str
    category: str
    event_type: str
    authorized: str
    severity: str
    details: Optional[str] = None
    origin: str
    observable: bool


# ── Dashboard Schemas (legacy shape; extended in the dashboard task) ──────────
class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: Optional[str] = None
    status: str
    created_by: Optional[int] = None
    creator_username: Optional[str] = None
    created_at: datetime
    ended_at: Optional[datetime] = None
    seed: int


class DashboardSummary(BaseModel):
    total_runs: int
    active_runs: int
    completed_runs: int
    total_segments: int
    segments_by_state: dict
    system_status: str
    latest_run: Optional[RunResponse] = None
    telemetry_points: int


# ── Activity Schemas ───────────────────────────────────────────────────────────
class ActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    timestamp: datetime
    details: Optional[str] = None
