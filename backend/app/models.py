from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Index,
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    analyst = "analyst"


class RunStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    completed = "completed"


class IncidentSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class IncidentStatus(str, enum.Enum):
    open = "open"
    investigating = "investigating"
    resolved = "resolved"
    closed = "closed"


# ── Schema metadata ────────────────────────────────────────────────────────────
class Meta(Base):
    __tablename__ = "meta"

    key = Column(String(50), primary_key=True)
    value = Column(String(200), nullable=False)


# ── Users ──────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default=UserRole.analyst.value, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    runs = relationship("Run", back_populates="creator")
    activities = relationship("ActivityLog", back_populates="user")


# ── Pipeline Topology ──────────────────────────────────────────────────────────
class Segment(Base):
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    segment_type = Column(String(50), nullable=False)  # terminal, pipeline, pump_station, valve_station
    order_index = Column(Integer, default=0)
    lat_start = Column(Float, nullable=False)
    lon_start = Column(Float, nullable=False)
    lat_end = Column(Float, nullable=False)
    lon_end = Column(Float, nullable=False)
    length_km = Column(Float, default=0)
    diameter_mm = Column(Float, default=914)
    design_pressure_bar = Column(Float, default=82.7)
    equipment = Column(String(30), nullable=True)  # inlet_control, pump, valve, delivery_control
    config_json = Column(Text, default="{}")


# ── Simulation Runs ────────────────────────────────────────────────────────────
class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    scenario_type = Column(String(40), default="normal", nullable=False)
    method = Column(String(30), nullable=True)
    target_segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)
    scenario_params = Column(Text, default="{}")
    seed = Column(Integer, default=42)
    tick_seconds = Column(Integer, default=5)
    duration_ticks = Column(Integer, default=240)
    playback_speed = Column(Integer, default=10)
    started_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default=RunStatus.active.value)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=True)
    # Playback control (DH-02): wall-clock time the run was paused at, and the total seconds spent paused
    # (or rewound by a reset). The reveal clock subtracts both, so stored rows never change.
    paused_at = Column(DateTime, nullable=True)
    paused_seconds = Column(Float, nullable=False, default=0.0, server_default="0")

    creator = relationship("User", back_populates="runs")
    target_segment = relationship("Segment")
    model_version = relationship("ModelVersion")


# ── Telemetry (reported stream only) ───────────────────────────────────────────
class Telemetry(Base):
    __tablename__ = "telemetry"
    __table_args__ = (
        Index("ix_telemetry_run_tick", "run_id", "tick"),
        Index("ix_telemetry_run_seg_tick", "run_id", "segment_id", "tick"),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=False)
    tick = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    pressure_bar = Column(Float, nullable=False)
    flow_m3h = Column(Float, nullable=False)
    temperature_c = Column(Float, nullable=False)
    valve_open_pct = Column(Float, nullable=True)
    pump_speed_pct = Column(Float, nullable=True)
    valve_state = Column(String(20), nullable=True)
    equipment_state = Column(String(20), nullable=True)


# ── Ground truth (never read by the analysis) ──────────────────────────────────
class GroundTruthTelemetry(Base):
    __tablename__ = "ground_truth_telemetry"
    __table_args__ = (
        Index("ix_gt_run_tick", "run_id", "tick"),
        Index("ix_gt_run_seg_tick", "run_id", "segment_id", "tick"),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=False)
    tick = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    actual_pressure_bar = Column(Float, nullable=False)
    actual_flow_m3h = Column(Float, nullable=False)
    actual_temperature_c = Column(Float, nullable=False)
    actual_valve_open_pct = Column(Float, nullable=True)
    actual_pump_speed_pct = Column(Float, nullable=True)
    phase = Column(String(20), nullable=False)
    is_target = Column(Boolean, default=False)
    process_affected = Column(Boolean, default=False)
    reporting_compromised = Column(Boolean, default=False)


class ScenarioGroundTruth(Base):
    __tablename__ = "scenario_ground_truth"

    run_id = Column(Integer, ForeignKey("runs.id"), primary_key=True)
    scenario_type = Column(String(40), nullable=False)
    method = Column(String(30), nullable=True)
    target_segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)
    event_start_tick = Column(Integer, nullable=True)
    event_peak_tick = Column(Integer, nullable=True)
    event_end_tick = Column(Integer, nullable=True)
    expected_root_cause = Column(String(80), nullable=False)
    manipulated_signal_or_asset = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)


# ── Control / security / analysis event stream ─────────────────────────────────
class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_run_tick", "run_id", "tick"),)

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)
    tick = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    source = Column(String(40), nullable=False)
    category = Column(String(20), nullable=False)  # control, security, device, process, analysis
    event_type = Column(String(60), nullable=False)
    authorized = Column(String(10), nullable=False, default="n/a")  # yes, no, unknown, n/a
    severity = Column(String(10), nullable=False, default="low")
    details = Column(Text, nullable=True)
    observable = Column(Boolean, nullable=False, default=True)
    origin = Column(String(10), nullable=False, default="simulator")  # simulator, analysis
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=True)


# ── Model registry ─────────────────────────────────────────────────────────────
class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True)
    version = Column(Integer, unique=True, nullable=False)
    algorithm = Column(String(40), default="isolation_forest")
    params_json = Column(Text, default="{}")
    dataset_json = Column(Text, default="{}")
    feature_spec = Column(String(20), nullable=True)
    metrics_json = Column(Text, default="{}")
    targets_json = Column(Text, default="{}")
    threshold = Column(Float, default=0.5)
    status = Column(String(20), default="training")  # training, ready, failed
    is_active = Column(Boolean, default=False)
    artifact_path = Column(String(300), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    trained_seconds = Column(Float, nullable=True)
    error = Column(Text, nullable=True)


# ── Analysis output ────────────────────────────────────────────────────────────
class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        Index("ix_results_run_tick", "run_id", "tick"),
        Index("ix_results_run_seg_tick", "run_id", "segment_id", "tick"),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=False)
    tick = Column(Integer, nullable=False)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=True)
    anomaly_score = Column(Float, nullable=True)
    ml_flag = Column(Boolean, default=False)
    # Null when the outcome is Insufficient. No default: an ORM bulk insert would turn None into it.
    trust_score = Column(Float, nullable=True)
    trust_status = Column(String(20), nullable=False, default="Supported")
    trust_factors = Column(Text, default="[]")
    checks = Column(Text, default="{}")
    baseline_alarms = Column(Text, default="{}")
    state = Column(String(20), nullable=False, default="normal")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (Index("ix_alerts_run", "run_id"),)

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=False)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=True)
    start_tick = Column(Integer, nullable=False)
    end_tick = Column(Integer, nullable=False)
    peak_tick = Column(Integer, nullable=False)
    peak_score = Column(Float, nullable=True)
    min_trust = Column(Float, nullable=False)
    kinds = Column(Text, default="[]")
    severity = Column(String(10), nullable=False)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Incidents and evaluation (Sprint 3) ────────────────────────────────────────
class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (Index("ix_incidents_run", "run_id"),)

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    key = Column(String(40), unique=True, nullable=False)
    model_version_id = Column(Integer, ForeignKey("model_versions.id"), nullable=True)
    engine_version = Column(String(10))
    start_tick = Column(Integer)
    end_tick = Column(Integer)
    detected_tick = Column(Integer)
    classification = Column(String(30))
    confidence = Column(Float)
    segment_code = Column(String(10), nullable=True)
    ot_layers = Column(Text, default="[]")
    localisation_note = Column(Text)
    severity = Column(String(10))
    summary = Column(Text)
    status = Column(String(15), default="investigating")
    status_note = Column(Text, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    payload = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True)
    version = Column(Integer, unique=True, nullable=False)
    status = Column(String(10), default="running")  # running, ready, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    model_version = Column(Integer, nullable=True)
    engine_version = Column(String(10))
    results = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    seconds = Column(Float, nullable=True)
    shipped = Column(Boolean, default=False)


# ── Activity Log ───────────────────────────────────────────────────────────────
class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)  # login, scenario_launched, model_trained, ...
    entity_type = Column(String(50), nullable=True)  # run, user, model
    entity_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(Text, nullable=True)

    user = relationship("User", back_populates="activities")
