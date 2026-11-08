def test_register_and_login(client):
    r = client.post("/api/v1/auth/register", json={"email": "a@b.dev", "password": "secret123"})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"user_id", "token"}

    r = client.post("/api/v1/auth/register", json={"email": "a@b.dev", "password": "secret123"})
    assert r.status_code == 409
    assert r.json()["error_code"] == "EMAIL_ALREADY_EXISTS"

    r = client.post("/api/v1/auth/login", json={"email": "a@b.dev", "password": "wrong"})
    assert r.status_code == 401
    assert r.json()["error_code"] == "AUTH_FAILED"

    r = client.post("/api/v1/auth/login", json={"email": "a@b.dev", "password": "secret123"})
    assert r.status_code == 200
    assert "token" in r.json()


def test_register_validation(client):
    r = client.post("/api/v1/auth/register", json={"email": "nope", "password": "secret123"})
    assert r.status_code == 422

    r = client.post("/api/v1/auth/register", json={"email": "a@b.dev", "password": "123"})
    assert r.status_code == 422


def test_protected_requires_token(client):
    r = client.get("/api/v1/connections")
    assert r.status_code == 401
    assert r.json()["error_code"] == "AUTH_REQUIRED"
