from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from app.database import Base
import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    analyst = "analyst"


class RunStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    stopped = "stopped"
    scheduled = "scheduled"


class SegmentState(str, enum.Enum):
    operational = "operational"
    warning = "warning"
    critical = "critical"
    offline = "offline"
    maintenance = "maintenance"


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
    name = Column(String(100), nullable=False)
    segment_type = Column(String(50), nullable=False)  # pipeline, pump_station, terminal, valve_station
    lat_start = Column(Float, nullable=False)
    lon_start = Column(Float, nullable=False)
    lat_end = Column(Float, nullable=False)
    lon_end = Column(Float, nullable=False)
    length_km = Column(Float, default=0)
    diameter_inches = Column(Float, default=36)
    max_pressure_psi = Column(Float, default=1200)
    state = Column(String(20), default=SegmentState.operational.value)
    order_index = Column(Integer, default=0)
    config_json = Column(Text, default="{}")

    telemetry = relationship("Telemetry", back_populates="segment")
    control_events = relationship("ControlEvent", back_populates="segment")
    incidents = relationship("Incident", back_populates="segment")


# ── Simulation Runs ────────────────────────────────────────────────────────────
class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), default=RunStatus.active.value)
    config_json = Column(Text, default="{}")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    seed = Column(Integer, default=42)

    creator = relationship("User", back_populates="runs")
    telemetry = relationship("Telemetry", back_populates="run")
    control_events = relationship("ControlEvent", back_populates="run")
    security_events = relationship("SecurityEvent", back_populates="run")
    incidents = relationship("Incident", back_populates="run")


# ── Telemetry ──────────────────────────────────────────────────────────────────
class Telemetry(Base):
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    pressure_psi = Column(Float, nullable=False)
    flow_rate_bph = Column(Float, nullable=False)
    temperature_f = Column(Float, nullable=False)
    is_ground_truth = Column(Boolean, default=False)

    run = relationship("Run", back_populates="telemetry")
    segment = relationship("Segment", back_populates="telemetry")


# ── Control Events ─────────────────────────────────────────────────────────────
class ControlEvent(Base):
    __tablename__ = "control_events"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    event_type = Column(String(50), nullable=False)  # valve_open, valve_close, pump_start, pump_stop
    valve_state = Column(String(20), nullable=True)  # open, closed, partial
    details = Column(Text, nullable=True)

    run = relationship("Run", back_populates="control_events")
    segment = relationship("Segment", back_populates="control_events")


# ── Security Events ────────────────────────────────────────────────────────────
class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)
    timestamp = Column(DateTime, nullable=False)
    severity = Column(String(20), nullable=False)
    event_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)

    run = relationship("Run", back_populates="security_events")


# ── Incidents ──────────────────────────────────────────────────────────────────
class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    incident_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    status = Column(String(20), default=IncidentStatus.open.value)
    description = Column(Text, nullable=True)

    run = relationship("Run", back_populates="incidents")
    segment = relationship("Segment", back_populates="incidents")


# ── Activity Log ───────────────────────────────────────────────────────────────
class ActivityLog(Base):
    __tablename__ = "activity_log"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(50), nullable=False)  # login, run_created, model_trained, user_created
    entity_type = Column(String(50), nullable=True)  # run, user, model
    entity_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(Text, nullable=True)

    user = relationship("User", back_populates="activities")
