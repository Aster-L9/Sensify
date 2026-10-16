import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text

from app.migrate import migrate_if_needed
from app.models import Segment

SPRINT1_SCHEMA = """
CREATE TABLE users (id INTEGER PRIMARY KEY, username VARCHAR(50) NOT NULL UNIQUE, email VARCHAR(100) NOT NULL UNIQUE,
    hashed_password VARCHAR(255) NOT NULL, role VARCHAR(20) NOT NULL, is_active BOOLEAN, created_at DATETIME, last_login DATETIME);
CREATE TABLE segments (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, segment_type VARCHAR(50) NOT NULL,
    lat_start FLOAT, lon_start FLOAT, lat_end FLOAT, lon_end FLOAT, length_km FLOAT, diameter_inches FLOAT,
    max_pressure_psi FLOAT, state VARCHAR(20), order_index INTEGER, config_json TEXT);
CREATE TABLE runs (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, description TEXT, status VARCHAR(20),
    config_json TEXT, created_by INTEGER, created_at DATETIME, ended_at DATETIME, seed INTEGER);
CREATE TABLE telemetry (id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, segment_id INTEGER NOT NULL, timestamp DATETIME NOT NULL,
    pressure_psi FLOAT NOT NULL, flow_rate_bph FLOAT NOT NULL, temperature_f FLOAT NOT NULL, is_ground_truth BOOLEAN);
CREATE TABLE control_events (id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, segment_id INTEGER NOT NULL,
    timestamp DATETIME NOT NULL, event_type VARCHAR(50) NOT NULL, valve_state VARCHAR(20), details TEXT);
CREATE TABLE activity_log (id INTEGER PRIMARY KEY, user_id INTEGER, action VARCHAR(50) NOT NULL, entity_type VARCHAR(50),
    entity_id INTEGER, timestamp DATETIME, details TEXT);
"""


def make_sprint1_db(path: Path) -> Path:
    con = sqlite3.connect(path)
    con.executescript(SPRINT1_SCHEMA)
    con.executemany("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)", [
        (1, "admin", "admin@sensify.local", "h1", "admin", 1, "2026-08-15 00:00:00.000000", None),
        (2, "analyst", "analyst@sensify.local", "h2", "analyst", 1, "2026-08-30 00:00:00.000000", "2026-09-28 10:00:00.000000"),
        (3, "extra", "extra@example.com", "h3", "analyst", 0, "2026-09-20 00:00:00.000000", None),
    ])
    con.execute("INSERT INTO runs (id, name, status, seed) VALUES (1, 'old run', 'active', 42)")
    con.execute("INSERT INTO telemetry (run_id, segment_id, timestamp, pressure_psi, flow_rate_bph, temperature_f, is_ground_truth) "
                "VALUES (1, 1, '2026-09-01 00:00:00', 1000, 800, 80, 0)")
    con.commit()
    con.close()
    return path


def insert_run_row(engine):
    with engine.begin() as c:
        c.execute(text("INSERT INTO runs (name, scenario_type, status, seed, tick_seconds, duration_ticks, playback_speed, started_at, created_at) "
                       "VALUES ('r', 'normal', 'completed', 1, 5, 240, 10, '2026-10-01 00:00:00', '2026-10-01 00:00:00')"))


def test_rebuilds_sprint1_db_and_keeps_users(tmp_path):
    db = make_sprint1_db(tmp_path / "old.db")
    eng = create_engine(f"sqlite:///{db}")
    assert migrate_if_needed(eng) is True
    assert (tmp_path / "old.db.sprint1.bak").exists()
    with eng.connect() as c:
        assert c.execute(text("select value from meta where key='schema_version'")).scalar() == "2"
        assert c.execute(text("select count(*) from users")).scalar() == 3
        assert c.execute(text("select count(*) from runs")).scalar() == 0
        assert c.execute(text("select hashed_password from users where username='extra'")).scalar() == "h3"
    eng.dispose()


def test_migrate_is_noop_on_v2(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'v2.db'}")
    migrate_if_needed(eng)
    insert_run_row(eng)
    assert migrate_if_needed(eng) is False
    with eng.connect() as c:
        assert c.execute(text("select count(*) from runs")).scalar() == 1
    eng.dispose()


def test_seed_creates_segments_in_bar(client, db):
    segs = db.query(Segment).order_by(Segment.order_index).all()
    assert [s.code for s in segs] == ["SEG-01", "SEG-02", "SEG-03", "SEG-04", "SEG-05", "SEG-06"]
    assert segs[2].equipment == "pump" and segs[4].design_pressure_bar == 82.7
