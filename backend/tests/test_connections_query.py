import json

import pytest


@pytest.fixture()
def fake_connection(auth_client, monkeypatch):
    from app import schema_cache
    from app.routers import router_connections, router_query

    def fake_check(conn, password):
        assert password == "s3cret"

    def fake_extract(conn, password):
        return ([{"schema": "public", "table": "users", "columns": [
            {"name": "id", "type": "int8", "nullable": False, "is_pk": True, "fk_target": None},
            {"name": "created_at", "type": "timestamp", "nullable": True, "is_pk": False, "fk_target": None},
        ]}], False)

    monkeypatch.setattr(router_connections, "check_connection", fake_check)
    monkeypatch.setattr(router_connections, "extract_schema", fake_extract)
    monkeypatch.setattr(schema_cache, "extract_schema", fake_extract)
    monkeypatch.setattr(router_query, "run_read_only_query", lambda *a, **k: pytest.fail("not reached"))

    r = auth_client.post("/api/v1/connections", json={
        "name": "main", "host": "localhost", "port": 5432,
        "db_name": "app", "db_user": "readonly_user", "db_password": "s3cret",
        "ssl_mode": "disable",
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "active"
    assert "db_password" not in body and "password" not in json.dumps(body)
    return body["id"]


def test_connection_never_returns_secret(auth_client, fake_connection):
    r = auth_client.get("/api/v1/connections")
    assert r.status_code == 200
    text = json.dumps(r.json())
    assert "s3cret" not in text and "password" not in text


def test_schema_endpoint(auth_client, fake_connection, monkeypatch):
    r = auth_client.get(f"/api/v1/connections/{fake_connection}/schema")
    assert r.status_code == 200
    body = r.json()
    assert body["tables"][0]["table"] == "users"
    assert body["truncated"] is False
    assert body["token_count"] > 0

    # cached now: second call served from snapshot
    r2 = auth_client.get(f"/api/v1/connections/{fake_connection}/schema")
    assert r2.status_code == 200


def test_schema_unknown_connection(auth_client):
    r = auth_client.get("/api/v1/connections/00000000-0000-0000-0000-000000000000/schema")
    assert r.status_code == 404
    assert r.json()["error_code"] == "CONNECTION_NOT_FOUND"


def test_query_validation_errors(auth_client, fake_connection):
    r = auth_client.post("/api/v1/query", json={"connection_id": "not-a-uuid", "prompt": "x"})
    assert r.status_code == 422

    r = auth_client.post("/api/v1/query", json={"connection_id": fake_connection, "prompt": "  "})
    assert r.status_code in (400, 422)

    r = auth_client.post("/api/v1/query", json={"connection_id": fake_connection, "prompt": "вопрос" * 700})
    assert r.status_code == 400
    assert r.json()["error_code"] == "VALIDATION_ERROR"


def test_query_e2e_mocked_llm(auth_client, fake_connection, monkeypatch):
    from app.routers import router_query
    from app.pg_client import QueryResult

    captured_prompt = {}

    def fake_llm(prompt):
        captured_prompt["value"] = prompt
        return "```sql\nSELECT date_trunc('week', created_at) AS w, count(*) AS cnt FROM users GROUP BY 1 ORDER BY 1\n```"

    def fake_run(conn, password, sql, row_limit=None):
        return QueryResult(columns=["w", "cnt"], rows=[["2026-08-03T00:00:00", 5]], truncated=False)

    monkeypatch.setattr(router_query, "call_llm", fake_llm)
    monkeypatch.setattr(router_query, "run_read_only_query", fake_run)

    r = auth_client.post("/api/v1/query", json={"connection_id": fake_connection, "prompt": "сравни регистрации по неделям"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 1
    assert body["chart_type"] == "line"
    assert body["chart_spec"]["x"] == "w"
    assert body["truncated"] is False
    assert body["duration_ms"] >= 0
    assert body["conversation_id"]
    # LLM saw the schema but no rows
    assert '"users"' in captured_prompt["value"]
    assert "сравни регистрации по неделям" in captured_prompt["value"]

    # history stored without raw data
    r = auth_client.get(f"/api/v1/history?connection_id={fake_connection}")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 1
    assert items[0]["execution_status"] == "success"
    assert items[0]["generated_sql"].startswith("SELECT date_trunc")


def test_query_llm_refuses(auth_client, fake_connection, monkeypatch):
    from app.routers import router_query

    monkeypatch.setattr(router_query, "call_llm", lambda prompt: "CANNOT_GENERATE")
    r = auth_client.post("/api/v1/query", json={"connection_id": fake_connection, "prompt": "а теперь прогноз"})
    assert r.status_code == 400
    assert r.json()["error_code"] == "VALIDATION_ERROR"


def test_query_rejects_dangerous_sql(auth_client, fake_connection, monkeypatch):
    from app.routers import router_query

    monkeypatch.setattr(router_query, "call_llm", lambda prompt: "DROP TABLE users")
    r = auth_client.post("/api/v1/query", json={"connection_id": fake_connection, "prompt": "удали всех"})
    assert r.status_code == 400
    assert r.json()["error_code"] == "SQL_NOT_SELECT"


def test_query_db_timeout(auth_client, fake_connection, monkeypatch):
    from app.errors import ApiError
    from app.routers import router_query
    from app.pg_client import QueryResult

    monkeypatch.setattr(router_query, "call_llm", lambda prompt: "SELECT 1")
    monkeypatch.setattr(
        router_query, "run_read_only_query",
        lambda *a, **k: (_ for _ in ()).throw(ApiError(504, "DB_TIMEOUT", "Запрос выполнялся слишком долго.")),
    )
    r = auth_client.post("/api/v1/query", json={"connection_id": fake_connection, "prompt": "долгий вопрос"})
    assert r.status_code == 504
    assert r.json()["error_code"] == "DB_TIMEOUT"
