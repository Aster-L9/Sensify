"""Shared fixtures. Environment is set before `app` is imported so tests never touch the demo database."""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="sensify-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["SEED_DEMO_RUNS"] = "0"
os.environ["JWT_SECRET"] = "test-only-jwt-secret-not-for-deployment"
os.environ["ADMIN_EMAIL"] = "admin@sensify.local"
os.environ["ADMIN_PASSWORD"] = "test-only-admin-password"
os.environ["ANALYST_PASSWORD"] = "test-only-analyst-password"
os.environ["MODEL_STORE_DIR"] = str(_TMP / "model_store")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email: str, password: str) -> dict:
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin_headers(client):
    return _login(client, "admin@sensify.local", os.environ["ADMIN_PASSWORD"])


@pytest.fixture(scope="session")
def analyst_headers(client):
    return _login(client, "analyst@sensify.local", os.environ["ANALYST_PASSWORD"])


@pytest.fixture
def db(client):
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def tiny_model(client):
    """A small model trained on a tiny generated dataset, registered and activated as v1."""
    from app.models import ModelVersion
    from app.services import registry
    from ml.generate_dataset import generate_dataset
    from ml.train import TrainParams, train_model

    data = _TMP / "tiny_data"
    os.environ["SENSIFY_DATASET_DIR"] = str(data)
    session = SessionLocal()
    try:
        if not session.query(ModelVersion).filter(ModelVersion.version == 1).first():
            generate_dataset(data, seed=5, n_train_normal=6, n_val_normal=3, n_val_scenario=5,
                             n_test_normal=2, n_test_scenario=5)
            train_model(TrainParams(n_estimators=30), data, registry.model_store_dir(), version=1)
            registry.register_from_dir(session, registry.model_store_dir() / "v1", None, activate_now=True)
        return 1
    finally:
        session.close()


@pytest.fixture
def no_active_model(tiny_model):
    from app.models import ModelVersion

    session = SessionLocal()
    active = [mv.id for mv in session.query(ModelVersion).filter(ModelVersion.is_active.is_(True))]
    for mv in session.query(ModelVersion).all():
        mv.is_active = False
    session.commit()
    try:
        yield
    finally:
        for mv in session.query(ModelVersion).filter(ModelVersion.id.in_(active)):
            mv.is_active = True
        session.commit()
        session.close()
