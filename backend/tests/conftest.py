import os
import tempfile

import pytest
from cryptography.fernet import Fernet


@pytest.fixture(scope="session", autouse=True)
def _env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("promptstat")
    os.environ["INTERNAL_DATABASE_URL"] = f"sqlite:///{tmp}/test.db"
    os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
    os.environ["JWT_SECRET"] = "test-secret"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "100"
    from app.config import get_settings
    get_settings.cache_clear()
    yield


@pytest.fixture()
def client():
    from app.db import Base, engine
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_client(client):
    r = client.post("/api/v1/auth/register", json={"email": "user@test.dev", "password": "secret123"})
    assert r.status_code == 200
    token = r.json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
