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
        assert c.execute(text("select value from meta where key='schema_version'")).scalar() == "4"
        assert c.execute(text("select count(*) from users")).scalar() == 3
        assert c.execute(text("select count(*) from runs")).scalar() == 0
        assert c.execute(text("select hashed_password from users where username='extra'")).scalar() == "h3"
    eng.dispose()


def test_migrate_is_noop_on_current_version(tmp_path):
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


def test_v2_upgrades_to_current_and_keeps_runs_and_users(tmp_path):
    from sqlalchemy import inspect
    from app.database import Base
    from app.models import Meta
    eng = create_engine(f"sqlite:///{tmp_path / 'v2.db'}")
    Base.metadata.create_all(eng)
    with eng.begin() as c:
        c.execute(Meta.__table__.insert(), [{"key": "schema_version", "value": "2"}])
        c.execute(text("INSERT INTO users (username, email, hashed_password, role, is_active) VALUES ('u','u@x','h','analyst',1)"))
        c.execute(text("DROP TABLE incidents"))
        c.execute(text("CREATE TABLE incidents (id INTEGER PRIMARY KEY, run_id INTEGER, old_col TEXT)"))
        c.execute(text("DROP TABLE evaluation_runs"))
    insert_run_row(eng)
    assert migrate_if_needed(eng) is True
    with eng.connect() as c:
        assert c.execute(text("select value from meta where key='schema_version'")).scalar() == "4"
        assert c.execute(text("select count(*) from runs")).scalar() == 1
        assert c.execute(text("select count(*) from users")).scalar() == 1
    insp = inspect(eng)
    assert "evaluation_runs" in insp.get_table_names()
    assert "key" in [col["name"] for col in insp.get_columns("incidents")]
    assert migrate_if_needed(eng) is False
    eng.dispose()


def test_v3_is_a_noop(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 'v3.db'}")
    assert migrate_if_needed(eng) is True
    assert migrate_if_needed(eng) is False
    eng.dispose()


def test_v3_to_v4_adds_playback_columns_and_keeps_analysis_rows(tmp_path):
    """A real v3 shape: runs without playback columns, analysis_results with a NOT NULL trust score."""
    from sqlalchemy import inspect
    from app.database import Base
    from app.models import Meta
    eng = create_engine(f"sqlite:///{tmp_path / 'v3.db'}")
    Base.metadata.create_all(eng)
    with eng.begin() as c:
        c.execute(Meta.__table__.insert(), [{"key": "schema_version", "value": "3"}])
        c.execute(text("ALTER TABLE runs DROP COLUMN paused_at"))
        c.execute(text("ALTER TABLE runs DROP COLUMN paused_seconds"))
        c.execute(text("DROP TABLE analysis_results"))
        c.execute(text("CREATE TABLE analysis_results (id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, "
                       "segment_id INTEGER NOT NULL, tick INTEGER NOT NULL, model_version_id INTEGER, anomaly_score FLOAT, "
                       "ml_flag BOOLEAN, trust_score FLOAT NOT NULL, trust_status VARCHAR(20) NOT NULL, trust_factors TEXT, "
                       "checks TEXT, baseline_alarms TEXT, state VARCHAR(20) NOT NULL)"))
        c.execute(text("CREATE INDEX ix_results_run_tick ON analysis_results (run_id, tick)"))
        c.execute(text("INSERT INTO analysis_results (run_id, segment_id, tick, anomaly_score, ml_flag, trust_score, "
                       "trust_status, trust_factors, checks, baseline_alarms, state) "
                       "VALUES (1, 1, 0, 0.1, 0, 0.93, 'Supported', '[]', '{}', '{}', 'normal')"))
    insert_run_row(eng)
    assert migrate_if_needed(eng) is True
    insp = inspect(eng)
    assert {"paused_at", "paused_seconds"} <= {col["name"] for col in insp.get_columns("runs")}
    trust = next(col for col in insp.get_columns("analysis_results") if col["name"] == "trust_score")
    assert trust["nullable"]
    with eng.connect() as c:
        assert c.execute(text("select value from meta where key='schema_version'")).scalar() == "4"
        assert c.execute(text("select trust_score, trust_status from analysis_results")).one() == (0.93, "Supported")
        assert c.execute(text("select paused_seconds from runs")).scalar() == 0
    assert "analysis_results_v3" not in insp.get_table_names()
    assert migrate_if_needed(eng) is False
    eng.dispose()
