from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


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
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


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
    id: int
    name: str
    segment_type: str
    lat_start: float
    lon_start: float
    lat_end: float
    lon_end: float
    length_km: float
    diameter_inches: float
    max_pressure_psi: float
    state: str
    order_index: int

    class Config:
        from_attributes = True


class TopologyResponse(BaseModel):
    segments: List[SegmentResponse]
    total_length_km: float
    segment_count: int


# ── Run Schemas ────────────────────────────────────────────────────────────────
class RunCreate(BaseModel):
    name: str
    description: Optional[str] = None
    config_json: Optional[str] = "{}"
    seed: Optional[int] = 42


class RunResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str
    config_json: Optional[str] = None
    created_by: Optional[int] = None
    creator_username: Optional[str] = None
    created_at: datetime
    ended_at: Optional[datetime] = None
    seed: int

    class Config:
        from_attributes = True


class RunStateResponse(BaseModel):
    run_id: int
    status: str
    segments: List[dict]
    telemetry_count: int
    latest_telemetry: Optional[datetime] = None


# ── Telemetry Schemas ──────────────────────────────────────────────────────────
class TelemetryResponse(BaseModel):
    id: int
    run_id: int
    segment_id: int
    timestamp: datetime
    pressure_psi: float
    flow_rate_bph: float
    temperature_f: float
    is_ground_truth: bool

    class Config:
        from_attributes = True


class TelemetryQuery(BaseModel):
    run_id: int
    segment_id: Optional[int] = None
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    ground_truth: Optional[bool] = None
    limit: int = 500


# ── Dashboard Schemas ──────────────────────────────────────────────────────────
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
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    timestamp: datetime
    details: Optional[str] = None

    class Config:
        from_attributes = True
