"""Regression tests for the Sprint 03 developer handover defects DH-01 to DH-10 (backend parts).

Every account created here is a fresh, uniquely named test account in the session's temporary database.
"""
import json
import uuid
from datetime import datetime, timedelta

import numpy as np
import pytest

from app.models import ModelVersion, Run, Telemetry, User
from app.services import registry
from app.services import runs as runs_service
from app.services.accounts import AccountError, normalise_email
from tests.helpers import launch, rep


def _fresh(prefix: str) -> dict:
    tag = uuid.uuid4().hex[:8]
    return {"username": f"{prefix}_{tag}", "email": f"{prefix}_{tag}@test.example", "password": f"pw-{tag}-ok"}


def _login(client, email, password):
    return client.post("/auth/login", json={"email": email, "password": password})


# ── DH-01: Admin account creation ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("role", ["analyst", "admin"])
def test_admin_creates_accounts_that_can_sign_in(client, admin_headers, db, role):
    body = _fresh("dh01") | {"role": role}
    r = client.post("/users/", json=body, headers=admin_headers)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["role"] == role and out["is_active"] and out["email"] == body["email"]
    assert not {"password", "hashed_password"} & out.keys()
    login = _login(client, body["email"], body["password"])
    assert login.status_code == 200 and login.json()["user"]["role"] == role


def test_admin_create_rejects_bad_and_duplicate_input_without_records(client, admin_headers, db):
    base = _fresh("dh01bad")
    before = db.query(User).count()
    for bad in ({"email": "@"}, {"email": "a@@b.com"}, {"username": "  "}, {"password": "123"}):
        assert client.post("/users/", json=base | bad, headers=admin_headers).status_code == 400
    assert client.post("/users/", json=base | {"role": "superuser"}, headers=admin_headers).status_code == 422
    assert client.post("/users/", json=base | {"hashed_password": "x"}, headers=admin_headers).status_code == 422
    db.expire_all()
    assert db.query(User).count() == before
    assert client.post("/users/", json=base, headers=admin_headers).status_code == 201
    dup = _fresh("dh01dup") | {"email": base["email"].upper()}
    assert client.post("/users/", json=dup, headers=admin_headers).json()["detail"] == "Email already registered"


def test_only_admins_can_create_users(client, analyst_headers):
    body = _fresh("dh01x") | {"role": "admin"}
    assert client.post("/users/", json=body, headers=analyst_headers).status_code == 403
    assert client.post("/users/", json=body).status_code in (401, 403)
    assert _login(client, body["email"], body["password"]).status_code == 401


# ── DH-03: email syntax ──────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("email", ["@", "a@", "@b.com", "a@@b.com", "a@b@c.com", "a b@c.com", "a@b", "a@.com",
                                   ".a@b.com", "a..b@c.com", "a@b..com", "a@-b.com"])
def test_malformed_email_is_rejected(email):
    with pytest.raises(AccountError):
        normalise_email(email)


@pytest.mark.parametrize("email", ["441234567@psu.edu.sa", "First.Last+tag@Example.COM ", "a_1@sub.domain.org"])
def test_valid_email_is_accepted_and_normalised(email):
    assert normalise_email(email) == email.strip().lower()


def test_register_rejects_bare_at_and_creates_nothing(client, db):
    body = _fresh("dh03") | {"email": "@"}
    r = client.post("/auth/register", json=body)
    assert r.status_code == 400 and "valid email" in r.json()["detail"]
    assert db.query(User).filter(User.username == body["username"]).first() is None
    good = _fresh("dh03ok")
    r = client.post("/auth/register", json=good)
    assert r.status_code == 200 and r.json()["user"]["role"] == "analyst"


# ── DH-04: supported roles only ──────────────────────────────────────────────────────────────────
def _new_analyst(client, admin_headers) -> dict:
    body = _fresh("dh04")
    out = client.post("/users/", json=body, headers=admin_headers).json()
    return out | {"password": body["password"]}


@pytest.mark.parametrize("role", ["unsupported_role", "", "Admin", 1, True, ["admin"]])
def test_unsupported_role_is_rejected_and_not_stored(client, admin_headers, db, role):
    user = _new_analyst(client, admin_headers)
    r = client.patch(f"/users/{user['id']}", json={"role": role}, headers=admin_headers)
    assert r.status_code == 422
    db.expire_all()
    assert db.get(User, user["id"]).role == "analyst"


def test_role_change_takes_effect_and_deactivation_blocks(client, admin_headers, analyst_headers):
    user = _new_analyst(client, admin_headers)
    token = _login(client, user["email"], user["password"]).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/users/", headers=headers).status_code == 403
    assert client.patch(f"/users/{user['id']}", json={"role": "admin"}, headers=admin_headers).status_code == 200
    assert client.get("/users/", headers=headers).status_code == 200  # same token, current role
    assert client.patch(f"/users/{user['id']}", json={"role": "analyst"}, headers=admin_headers).status_code == 200
    assert client.get("/users/", headers=headers).status_code == 403
    assert client.patch(f"/users/{user['id']}", json={"is_active": False}, headers=admin_headers).status_code == 200
    assert client.get("/auth/me", headers=headers).status_code == 403
    assert _login(client, user["email"], user["password"]).status_code == 403
    me = client.get("/auth/me", headers=analyst_headers).json()
    assert client.patch(f"/users/{me['id']}", json={"role": "admin"}, headers=analyst_headers).status_code == 403


def test_admin_cannot_lock_themselves_out(client, admin_headers):
    me = client.get("/auth/me", headers=admin_headers).json()
    assert client.patch(f"/users/{me['id']}", json={"role": "analyst"}, headers=admin_headers).status_code == 400
    assert client.patch(f"/users/{me['id']}", json={"is_active": False}, headers=admin_headers).status_code == 400
    assert client.get("/auth/me", headers=admin_headers).json()["role"] == "admin"


# ── DH-02: pause, resume, reset ──────────────────────────────────────────────────────────────────
@pytest.fixture
def clock(monkeypatch):
    state = {"now": datetime(2026, 9, 29, 12)}
    monkeypatch.setattr(runs_service, "utcnow", lambda: state["now"])
    return state


def _tick(client, headers, rid):
    return client.get(f"/runs/{rid}/state", headers=headers).json()["tick"]


def test_pause_freezes_every_view_and_resume_continues_without_a_jump(client, admin_headers, analyst_headers, clock, db):
    rid = launch(client, admin_headers, seed=11).json()["id"]  # 10x: 2 ticks per second
    clock["now"] += timedelta(seconds=10)
    assert _tick(client, admin_headers, rid) == 20
    r = client.post(f"/runs/{rid}/pause", headers=admin_headers)
    assert r.status_code == 200 and r.json()["status"] == "paused"
    clock["now"] += timedelta(minutes=3)
    assert _tick(client, admin_headers, rid) == 20 and _tick(client, analyst_headers, rid) == 20
    rows = client.get(f"/telemetry?run_id={rid}&segment_id=1", headers=analyst_headers).json()
    assert rows[-1]["tick"] == 20
    assert all(e["tick"] <= 20 for e in client.get(f"/runs/{rid}/events", headers=analyst_headers).json())
    assert client.get(f"/runs/{rid}", headers=analyst_headers).json()["status"] == "paused"
    # A restart: a fresh session reads the stored row and derives the same frozen tick.
    db.expire_all()
    run = db.get(Run, rid)
    assert runs_service.resolve_tick(run, None, clock["now"] + timedelta(hours=1)) == 20
    assert client.post(f"/runs/{rid}/pause", headers=admin_headers).status_code == 409
    assert client.post(f"/runs/{rid}/resume", headers=admin_headers).json()["status"] == "active"
    assert _tick(client, admin_headers, rid) == 20
    clock["now"] += timedelta(seconds=5)
    assert _tick(client, admin_headers, rid) == 30
    assert client.post(f"/runs/{rid}/resume", headers=admin_headers).status_code == 409


def test_reset_rewinds_the_same_run_and_replays_identical_values(client, admin_headers, clock):
    rid = launch(client, admin_headers, seed=12).json()["id"]
    clock["now"] += timedelta(seconds=30)
    before = client.get(f"/telemetry?run_id={rid}&segment_id=3", headers=admin_headers).json()
    r = client.post(f"/runs/{rid}/reset", headers=admin_headers).json()
    assert r["status"] == "paused" and r["revealed_ticks"] == 1 and r["seed"] == 12
    clock["now"] += timedelta(minutes=10)
    assert _tick(client, admin_headers, rid) == 0
    client.post(f"/runs/{rid}/resume", headers=admin_headers)
    clock["now"] += timedelta(seconds=30)
    after = client.get(f"/telemetry?run_id={rid}&segment_id=3", headers=admin_headers).json()
    assert [(a["tick"], a["pressure_bar"], a["flow_m3h"]) for a in after] == \
           [(b["tick"], b["pressure_bar"], b["flow_m3h"]) for b in before]
    # The same seed and settings in a new run reproduce the values at matching times.
    other = launch(client, admin_headers, seed=12).json()["id"]
    clock["now"] += timedelta(seconds=30)
    again = client.get(f"/telemetry?run_id={other}&segment_id=3", headers=admin_headers).json()
    assert [a["pressure_bar"] for a in again] == [b["pressure_bar"] for b in before]


def test_reset_of_a_completed_run_and_completion_after_pauses(client, admin_headers, clock):
    rid = launch(client, admin_headers, seed=13).json()["id"]
    clock["now"] += timedelta(hours=1)
    assert client.get(f"/runs/{rid}", headers=admin_headers).json()["status"] == "completed"
    assert client.post(f"/runs/{rid}/pause", headers=admin_headers).status_code == 409
    client.post(f"/runs/{rid}/reset", headers=admin_headers)
    client.post(f"/runs/{rid}/resume", headers=admin_headers)
    clock["now"] += timedelta(minutes=2)  # 240 ticks at 10x take 120 s
    out = client.get(f"/runs/{rid}", headers=admin_headers).json()
    assert out["status"] == "completed" and out["revealed_ticks"] == 240


def test_only_admins_control_playback(client, admin_headers, analyst_headers, clock):
    rid = launch(client, admin_headers).json()["id"]
    for action in ("pause", "resume", "reset"):
        assert client.post(f"/runs/{rid}/{action}", headers=analyst_headers).status_code == 403
    assert client.post("/runs/999999/pause", headers=admin_headers).status_code == 404


# ── DH-05: segment references ────────────────────────────────────────────────────────────────────
def test_invalid_and_missing_segments_are_errors_not_empty_data(client, analyst_headers, admin_headers, clock):
    rid = launch(client, admin_headers).json()["id"]
    clock["now"] += timedelta(seconds=10)
    for path in (f"/telemetry?run_id={rid}&segment_id=", f"/runs/{rid}/events?segment_id=", "/alerts?segment_id="):
        assert client.get(path + "-1", headers=analyst_headers).status_code == 422
        assert client.get(path + "0", headers=analyst_headers).status_code == 422
        assert client.get(path + "999999", headers=analyst_headers).status_code == 404
        assert client.get(path + "abc", headers=analyst_headers).status_code == 422
    assert client.get("/incidents?segment=SEG-99", headers=analyst_headers).status_code == 404
    # A real segment with no readings in range is a legitimate empty answer.
    r = client.get(f"/telemetry?run_id={rid}&segment_id=2&from_tick=200", headers=analyst_headers)
    assert r.status_code == 200 and r.json() == []
    rows = client.get(f"/telemetry?run_id={rid}&segment_id=2", headers=analyst_headers).json()
    assert rows and all(row["segment_code"] == "SEG-02" and row["run_id"] == rid for row in rows)
    assert client.get("/telemetry?run_id=999999&segment_id=2", headers=analyst_headers).status_code == 404
    assert client.get(f"/telemetry?run_id={rid}&from_tick=5&to_tick=2", headers=analyst_headers).status_code == 400
    assert client.get(f"/telemetry?run_id={rid}&from_tick=-1", headers=analyst_headers).status_code == 422


# ── DH-10: alert time filter ─────────────────────────────────────────────────────────────────────
def test_alert_time_filter_uses_window_overlap(client, admin_headers, analyst_headers, tiny_model, clock):
    rid = launch(client, admin_headers, scenario_type="telemetry_manipulation", method="replay",
                 target_segment="SEG-03", magnitude=0.9, onset_min=2).json()["id"]
    clock["now"] += timedelta(hours=1)
    items = client.get(f"/alerts?run_id={rid}", headers=analyst_headers).json()
    assert items
    first = min(items, key=lambda a: a["start_tick"])
    s, e = first["start_tick"], first["end_tick"]
    q = f"/alerts?run_id={rid}"
    assert client.get(f"{q}&from_tick=9999&to_tick=9999", headers=analyst_headers).json() == []
    inside = client.get(f"{q}&from_tick={s}&to_tick={s}", headers=analyst_headers).json()
    assert first["id"] in [a["id"] for a in inside]
    overlap = client.get(f"{q}&from_tick={e}", headers=analyst_headers).json()  # open at the start of the range
    assert first["id"] in [a["id"] for a in overlap] and all(a["end_tick"] >= e for a in overlap)
    before = client.get(f"{q}&to_tick={max(s - 1, 0)}", headers=analyst_headers).json()
    assert first["id"] not in [a["id"] for a in before] and all(a["start_tick"] <= s - 1 for a in before)
    combined = client.get(f"{q}&from_tick={s}&to_tick={e}&segment_id={first['segment_id']}&kind={first['kinds'][0]}",
                          headers=admin_headers).json()
    assert first["id"] in [a["id"] for a in combined]
    assert all(a["segment_id"] == first["segment_id"] for a in combined)
    assert len(client.get(f"{q}&from_tick=0&limit=1", headers=analyst_headers).json()) == 1
    assert client.get(f"{q}&from_tick=50&to_tick=10", headers=analyst_headers).status_code == 400
    assert client.get(f"{q}&from_tick=-3", headers=analyst_headers).status_code == 422


def test_alert_time_filter_never_reaches_past_the_reveal_cutoff(client, admin_headers, analyst_headers, tiny_model, clock):
    rid = launch(client, admin_headers, scenario_type="telemetry_manipulation", method="replay",
                 target_segment="SEG-03", magnitude=0.9, onset_min=2).json()["id"]
    clock["now"] += timedelta(seconds=40)  # 81 ticks revealed
    items = client.get(f"/alerts?run_id={rid}&from_tick=0&to_tick=239", headers=analyst_headers).json()
    assert all(a["end_tick"] <= 80 for a in items)


# ── DH-07: portable model artifact paths ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("stored", [
    r"C:\somewhere\else\model_store\v1\model.joblib",  # Windows drive path (read as relative on macOS before)
    r"\\fileserver\share\model_store\v1\model.joblib",  # UNC
    "/Users/someone/sensify/backend/model_store/v1/model.joblib",  # POSIX (read as relative on Windows before)
    "../../outside/model.joblib",  # escapes the store
    "v1/missing.joblib",  # relative but missing
])
def test_unusable_artifact_paths_fall_back_to_the_same_version(tiny_model, stored):
    mv = ModelVersion(version=1, artifact_path=stored)
    assert registry.artifact_file(mv) == registry.model_store_dir() / "v1" / "model.joblib"


def test_relative_artifact_paths_resolve_in_the_store(tiny_model):
    for stored in ("v1/model.joblib", r"v1\model.joblib"):
        assert registry.artifact_file(ModelVersion(version=1, artifact_path=stored)) == \
               registry.model_store_dir() / "v1" / "model.joblib"


def test_missing_artifact_is_a_clear_error(tiny_model):
    mv = ModelVersion(id=987654, version=99, artifact_path="v99/model.joblib")
    assert not registry.artifact_available(mv)
    with pytest.raises(registry.ArtifactUnavailable, match="v99"):
        registry.load_model(mv)


# ── DH-08: insufficient evidence is its own trust outcome ────────────────────────────────────────
@pytest.fixture(scope="module")
def ref():
    from app.analysis.reference import ReferenceProfile
    from tests.helpers import normal_runs

    return ReferenceProfile.fit(normal_runs(8, start_seed=300))


def _trust(run, ref):
    from app.analysis.consistency import run_checks
    from app.analysis.trust import compute_trust

    return compute_trust(run, run_checks(run, ref))


def test_all_missing_measurements_are_not_supported(ref):
    run = rep(scenario_type="normal", seed=6300)
    for arr in (run.pressure, run.flow, run.temperature):
        arr[:] = np.nan
    trust = _trust(run, ref)
    assert (trust.status == "Insufficient").all()
    assert np.isnan(trust.score).all()


def test_partial_gap_neighbour_gap_and_recovery(ref):
    from app.analysis.consistency import run_checks
    from app.analysis.trust import trust_factors

    run = rep(scenario_type="normal", seed=6400)
    run.pressure[100:120, 2] = np.nan  # SEG-03 drops out for 100 s
    run.flow[150:240:2, 4] = np.nan  # SEG-05 reports every other reading
    run.pressure[60:70, 1] = np.nan  # SEG-02 drops out: SEG-01 has no neighbour left
    trust = _trust(run, ref)
    assert (trust.status[100:120, 2] == "Insufficient").all()
    assert (trust.status[60:70, 0] == "Insufficient").all()
    assert (trust.status[60:70, 2] == "Supported").all()  # SEG-03 still has SEG-04 to compare with
    assert (trust.status[160:240, 4] == "Insufficient").all()  # too few recent readings, even when one arrives
    assert trust.status[122, 2] == "Insufficient"  # 3 of the last 6 readings missing
    assert trust.status[123, 2] == "Supported"  # 4 of the last 6 arrived
    assert (trust.status[130:150, 2] == "Supported").all()  # recovers once readings return
    assert not np.isnan(trust.score[130:150, 2]).any()
    assert (trust.status[:60, :] == "Supported").all()
    checks = run_checks(run, ref)
    detail = trust_factors(run, ref, checks, trust, 105, 2)
    assert detail[0]["code"] == "insufficient" and "No pressure reading from SEG-03" in detail[0]["detail"]
    assert "cannot be cross-checked" in trust_factors(run, ref, checks, trust, 65, 0)[0]["detail"]


def test_genuine_conflict_still_lowers_trust_with_gaps_elsewhere(ref):
    run = rep(scenario_type="telemetry_manipulation", method="replay", target_segment="SEG-03", seed=6401,
              onset_min=2, magnitude=0.9)
    run.pressure[10:20, 5] = np.nan
    trust = _trust(run, ref)
    assert (trust.status[:, 2] == "Contradicted").any()
    assert (trust.status[10:20, 5] == "Insufficient").all()


def test_persisted_incomplete_records_score_as_insufficient(client, admin_headers, analyst_headers, tiny_model, clock, db):
    rid = launch(client, admin_headers, scenario_type="normal", seed=6500).json()["id"]
    seg4 = 4
    db.query(Telemetry).filter(Telemetry.run_id == rid, Telemetry.segment_id == seg4,
                               Telemetry.tick.between(100, 140)).delete(synchronize_session=False)
    db.commit()
    assert client.post(f"/runs/{rid}/score", headers=admin_headers).status_code == 200
    clock["now"] += timedelta(hours=1)
    state = client.get(f"/runs/{rid}/state?at=120", headers=analyst_headers).json()
    seg = next(s for s in state["segments"] if s["segment_id"] == seg4)
    assert seg["state"] == "insufficient" and seg["trust_status"] == "Insufficient" and seg["trust_score"] is None
    assert seg["top_factor"]["code"] == "insufficient"
    later = next(s for s in client.get(f"/runs/{rid}/state?at=180", headers=analyst_headers).json()["segments"]
                 if s["segment_id"] == seg4)
    assert later["trust_status"] == "Supported"
    # Missing readings are not alerts: no flagged window is built from the gap alone.
    assert not [a for a in client.get(f"/alerts?run_id={rid}&segment_id={seg4}&from_tick=100&to_tick=140",
                                      headers=analyst_headers).json() if a["start_tick"] >= 100]
    trust = client.get(f"/runs/{rid}/telemetry-trust", headers=analyst_headers).json()
    series = next(s for s in trust["segments"] if s["segment_id"] == seg4)
    assert series["trust"][120] is None and series["status"][120] == "Insufficient"


# ── DH-09: validation outcomes apart from test metrics ───────────────────────────────────────────
def test_training_records_validation_outcomes_with_provenance(client, admin_headers, tiny_model):
    mv_id = next(m["id"] for m in client.get("/models", headers=admin_headers).json() if m["version"] == 1)
    detail = client.get(f"/models/{mv_id}", headers=admin_headers).json()
    val = detail["validation"]
    assert val and val["split"] == "validation" and val["computed"] == "at training"
    assert val["runs"] == val["normal_runs"] + val["scenario_runs"] == 8
    assert {"ml", "baseline", "trust"} <= val["metrics"].keys()
    assert val["metrics"]["ml"]["overall"]["total"] == val["scenario_runs"]
    assert detail["metrics"]["ml"]["overall"]["total"] == 5  # test split, unchanged and separate
    assert detail["artifact_available"] is True and detail["has_validation"] is True


def test_versions_without_validation_report_none(client, admin_headers, db, tiny_model):
    mv = ModelVersion(version=777, status="ready", metrics_json=json.dumps({"metrics": {}, "targets_check": {}}),
                      artifact_path="v777/model.joblib", created_at=datetime(2026, 1, 1))
    db.add(mv)
    db.commit()
    try:
        out = client.get(f"/models/{mv.id}", headers=admin_headers).json()
        assert out["validation"] is None and out["has_validation"] is False and out["artifact_available"] is False
        r = client.post(f"/models/{mv.id}/activate", headers=admin_headers)
        assert r.status_code == 400 and "missing" in r.json()["detail"]
    finally:
        db.delete(mv)
        db.commit()


def test_trust_handles_a_run_shorter_than_the_recent_window(ref):
    run = rep(scenario_type="normal", seed=6402)
    for name in ("pressure", "flow", "temperature", "valve_open", "pump_speed"):
        setattr(run, name, getattr(run, name)[:3].copy())
    run.flow[1, 0] = np.nan
    trust = _trust(run, ref)
    assert trust.status.shape == (3, 6) and trust.status[1, 0] == "Insufficient" and trust.status[2, 3] == "Supported"


# ── DH-07 follow-up: one portable stored form ────────────────────────────────────────────────────
def test_new_versions_store_a_portable_relative_path(db, tiny_model):
    mv = db.query(ModelVersion).filter(ModelVersion.version == 1).one()
    assert mv.artifact_path == "v1/model.joblib"
    assert registry._stored_path(registry.model_store_dir() / "v12") == "v12/model.joblib"


@pytest.mark.parametrize("legacy", [
    r"C:\Users\someone\sensify\backend\model_store\v1\model.joblib",
    r"\fileserver\share\model_store\v1\model.joblib",
    "/Users/someone/sensify/backend/model_store/v1/model.joblib",
    r"v1\model.joblib",
])
def test_startup_rewrites_legacy_paths_to_the_portable_form(db, tiny_model, legacy):
    mv = db.query(ModelVersion).filter(ModelVersion.version == 1).one()
    try:
        mv.artifact_path = legacy
        db.commit()
        assert registry.normalise_artifact_paths(db) == [1]
        db.refresh(mv)
        assert mv.artifact_path == "v1/model.joblib"
        assert registry.normalise_artifact_paths(db) == []  # already portable: nothing to do
    finally:
        mv.artifact_path = "v1/model.joblib"
        db.commit()


def test_a_path_without_a_store_copy_is_left_alone(db, tiny_model):
    mv = ModelVersion(version=778, status="ready", artifact_path=r"D:\elsewhere\v778\model.joblib",
                      created_at=datetime(2026, 1, 1))
    db.add(mv)
    db.commit()
    try:
        assert 778 not in registry.normalise_artifact_paths(db)
        db.refresh(mv)
        assert mv.artifact_path == r"D:\elsewhere\v778\model.joblib"
    finally:
        db.delete(mv)
        db.commit()


def test_relative_store_setting_is_relative_to_the_backend_folder(monkeypatch):
    monkeypatch.setenv("MODEL_STORE_DIR", "model_store")
    assert registry.model_store_dir() == registry.BACKEND_DIR / "model_store"
