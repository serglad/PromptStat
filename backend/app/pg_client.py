import json
import re
from dataclasses import dataclass
from decimal import Decimal
from datetime import date, datetime, time, timedelta, timezone

import psycopg2
import psycopg2.extensions  # noqa: F401  (ensures extensions/errors are loaded)

from .config import get_settings
from .errors import ApiError
from .models import Connection

COLUMNS_SQL = """
SELECT
  c.table_schema, c.table_name, c.column_name, c.data_type, c.is_nullable,
  COALESCE(
    (SELECT string_agg(
        quote_ident(ccu2.table_schema) || '.' || quote_ident(ccu2.table_name) || '(' || ccu2.column_name || ')', ', ' ORDER BY kcu2.ordinal_position)
     FROM information_schema.table_constraints tc
     JOIN information_schema.key_column_usage kcu
       ON kcu.constraint_name = tc.constraint_name AND kcu.table_schema = tc.table_schema
     JOIN information_schema.constraint_column_usage ccu2
       ON ccu2.constraint_name = tc.constraint_name AND ccu2.table_schema = tc.table_schema
     JOIN information_schema.key_column_usage kcu2
       ON kcu2.constraint_name = tc.constraint_name AND kcu2.table_schema = tc.table_schema
       AND kcu2.column_name = c.column_name
       AND kcu2.table_name = c.table_name AND kcu2.table_schema = c.table_schema
     WHERE tc.constraint_type = 'FOREIGN KEY'
       AND tc.table_schema = c.table_schema AND tc.table_name = c.table_name
       AND kcu.column_name = c.column_name
    ), '') AS fk_targets,
    EXISTS (
      SELECT 1 FROM information_schema.table_constraints tc2
      JOIN information_schema.key_column_usage kcu3
        ON kcu3.constraint_name = tc2.constraint_name AND kcu3.table_schema = tc2.table_schema
      WHERE tc2.constraint_type = 'PRIMARY KEY'
        AND tc2.table_schema = c.table_schema AND tc2.table_name = c.table_name
        AND kcu3.column_name = c.column_name AND kcu3.table_schema = c.table_schema
        AND kcu3.table_name = c.table_name
    ) AS is_pk
FROM information_schema.columns c
WHERE c.table_schema NOT IN ('pg_catalog','information_schema')
  AND c.table_schema NOT LIKE 'pg\\_temp\\_%' ESCAPE '\\'
  AND c.table_schema NOT LIKE 'pg\\_toast%' ESCAPE '\\'
ORDER BY c.table_schema, c.table_name, c.ordinal_position
"""


def _connect(conn: Connection, password: str, connect_timeout: int = 10):
    try:
        return psycopg2.connect(
            host=conn.db_host,
            port=conn.db_port,
            dbname=conn.db_name,
            user=conn.db_user,
            password=password,
            sslmode=conn.ssl_mode or "prefer",
            connect_timeout=connect_timeout,
        )
    except psycopg2.Error as exc:
        if "timeout" in str(exc).lower():
            raise ApiError(504, "DB_TIMEOUT", "База данных не отвечает.")
        raise ApiError(403, "DB_AUTH_FAILED", "Не удалось подключиться к базе данных.")


def check_connection(conn: Connection, password: str, connect_timeout: int = 10) -> None:
    pg = _connect(conn, password, connect_timeout=connect_timeout)
    try:
        pg.set_session(readonly=True, autocommit=False)
        with pg.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (get_settings().STATEMENT_TIMEOUT_MS,))
            cur.execute("SELECT 1")
            cur.fetchone()
            cur.execute(COLUMNS_SQL)
        pg.commit()
    except psycopg2.errors.QueryCanceled:
        raise ApiError(504, "DB_TIMEOUT", "База данных не отвечает.")
    except ApiError:
        raise
    except psycopg2.Error:
        raise ApiError(403, "DB_AUTH_FAILED", "Не удалось проверить доступ к базе данных.")
    finally:
        pg.close()


def extract_schema(conn: Connection, password: str) -> tuple[list[dict], bool]:
    """Return (tables, truncated) raw schema dicts, truncated to token budget."""
    pg = _connect(conn, password)
    try:
        pg.set_session(readonly=True, autocommit=False)
        with pg.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (get_settings().STATEMENT_TIMEOUT_MS,))
            cur.execute(COLUMNS_SQL)
            rows = cur.fetchall()
        pg.commit()
    except psycopg2.errors.QueryCanceled:
        raise ApiError(504, "DB_TIMEOUT", "База данных не отвечает.")
    except ApiError:
        raise
    except psycopg2.Error:
        raise ApiError(403, "DB_AUTH_FAILED", "Не удалось прочитать схему базы данных.")
    finally:
        pg.close()

    by_table: dict[tuple[str, str], dict] = {}
    for schema, table, col, dtype, nullable, fk_targets, is_pk in rows:
        key = (schema, table)
        t = by_table.setdefault(key, {"schema": schema, "table": table, "columns": []})
        t["columns"].append({
            "name": col,
            "type": dtype,
            "nullable": nullable == "YES",
            "is_pk": bool(is_pk),
            "fk_target": fk_targets or None,
        })

    tables = list(by_table.values())
    ref_count = _fk_ref_counts(tables)
    tables.sort(key=lambda t: (-ref_count.get((t["schema"], t["table"]), 0), t["schema"], t["table"]))

    settings = get_settings()
    kept: list[dict] = []
    truncated = False
    for t in tables:
        kept.append(t)
        if _schema_token_count(kept) > settings.SCHEMA_MAX_TOKENS:
            kept.pop()
            truncated = True
            break
    return kept, truncated


def _fk_ref_counts(tables: list[dict]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for t in tables:
        for col in t["columns"]:
            fk = col.get("fk_target")
            if not fk:
                continue
            for part in fk.split(", "):
                m = re.match(r'"?([A-Za-z0-9_$]+)"?\."?([A-Za-z0-9_$]+)"?\(', part)
                if m:
                    counts[(m.group(1), m.group(2))] = counts.get((m.group(1), m.group(2)), 0) + 1
    return counts


def _schema_token_count(tables: list[dict]) -> int:
    return len(json.dumps(tables, ensure_ascii=False, separators=(",", ":"))) // 4


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    truncated: bool


_JSON_SAFE = (type(None), bool, int, float, str)


def _json_value(v):
    if isinstance(v, _JSON_SAFE):
        return v
    if isinstance(v, Decimal):
        f = float(v)
        return int(f) if f.is_integer() and abs(f) < 1e15 else f
    if isinstance(v, (datetime, date, time)):
        return v.isoformat()
    if isinstance(v, timedelta):
        return str(v)
    if isinstance(v, (bytes, bytearray)):
        return v.hex()
    return str(v)


def run_read_only_query(conn: Connection, password: str, sql: str, row_limit: int | None = None) -> QueryResult:
    settings = get_settings()
    limit = row_limit or settings.DEFAULT_ROW_LIMIT
    pg = _connect(conn, password)
    try:
        pg.set_session(readonly=True, autocommit=False)
        with pg.cursor() as cur:
            cur.execute("SET statement_timeout = %s", (settings.STATEMENT_TIMEOUT_MS,))
            cur.execute("SET lock_timeout = %s", (settings.LOCK_TIMEOUT_MS,))
            cur.execute("SET idle_in_transaction_session_timeout = %s", (settings.IDLE_IN_TRANSACTION_TIMEOUT_MS,))
            wrapped = f"SELECT * FROM ({sql.rstrip().rstrip(';')}) AS _promptstat_q LIMIT {int(limit) + 1}"
            cur.execute(wrapped)
            columns = [d.name for d in cur.description] if cur.description else []
            fetched = cur.fetchmany(limit + 1)
            truncated = len(fetched) > limit
            rows = [[_json_value(v) for v in row] for row in fetched[:limit]]
        pg.rollback()
        return QueryResult(columns=columns, rows=rows, truncated=truncated)
    except psycopg2.errors.QueryCanceled:
        raise ApiError(504, "DB_TIMEOUT", "Запрос выполнялся слишком долго.")
    except psycopg2.errors.InsufficientPrivilege:
        raise ApiError(403, "DB_AUTH_FAILED", "У роли недостаточно прав для этого запроса.")
    except psycopg2.errors.SyntaxError:
        raise ApiError(400, "SQL_NOT_SELECT", "SQL содержит синтаксическую ошибку.")
    except psycopg2.errors.UndefinedTable:
        raise ApiError(400, "SQL_NOT_SELECT", "SQL ссылается на несуществующую таблицу или колонку.")
    except psycopg2.Error:
        raise ApiError(400, "SQL_NOT_SELECT", "Не удалось выполнить запрос.")
    finally:
        pg.close()
