import pytest

from app.errors import ApiError
from app.sql_guard import validate_sql

OK_CASES = [
    "SELECT 1",
    "WITH x AS (SELECT 1 AS n) SELECT * FROM x",
    "SELECT a FROM t1 UNION ALL SELECT b FROM t2",
    "SELECT date_trunc('week', created_at) w, count(*) FROM users GROUP BY 1 ORDER BY 1",
    "SELECT * FROM orders o JOIN users u ON u.id = o.user_id LIMIT 10",
]

BAD_CASES = [
    ("INSERT INTO t VALUES (1)", "SQL_NOT_SELECT"),
    ("UPDATE t SET a = 1", "SQL_NOT_SELECT"),
    ("DELETE FROM t", "SQL_NOT_SELECT"),
    ("DROP TABLE t", "SQL_NOT_SELECT"),
    ("SELECT 1; SELECT 2", "SQL_MULTIPLE_STATEMENTS"),
    ("SELECT 1; DROP TABLE users", "SQL_MULTIPLE_STATEMENTS"),
    ("WITH x AS (DELETE FROM t RETURNING *) SELECT * FROM x", "SQL_NOT_SELECT"),
    ("WITH x AS (INSERT INTO t VALUES (1) RETURNING id) SELECT * FROM x", "SQL_NOT_SELECT"),
    ("SELECT * FROM t FOR UPDATE", "SQL_NOT_SELECT"),
    ("SELECT * FROM t FOR SHARE", "SQL_NOT_SELECT"),
    ("SELECT * INTO tmp FROM t", "SQL_NOT_SELECT"),
    ("COPY t TO '/tmp/dump'", "SQL_NOT_SELECT"),
    ("CALL my_proc()", "SQL_NOT_SELECT"),
    ("DO $$ BEGIN END $$", "SQL_NOT_SELECT"),
    ("SET statement_timeout = 0", "SQL_NOT_SELECT"),
    ("BEGIN", "SQL_NOT_SELECT"),
    ("SELECT pg_sleep(60)", "SQL_NOT_SELECT"),
    ("SELECT * FROM t WHERE x = 'pg_sleep(1)'", "SQL_NOT_SELECT"),
    ("SELECT lo_import('/etc/passwd')", "SQL_NOT_SELECT"),
    ("SELECT pg_read_file('/etc/shadow')", "SQL_NOT_SELECT"),
    ("SELECT set_config('x','y',true)", "SQL_NOT_SELECT"),
    ("SELECT dblink('host=evil', 'SELECT 1')", "SQL_NOT_SELECT"),
    ("not valid sql !!!", "SQL_NOT_SELECT"),
]


@pytest.mark.parametrize("sql", OK_CASES)
def test_valid_selects_pass(sql):
    assert validate_sql(sql) == sql


@pytest.mark.parametrize("sql,code", BAD_CASES)
def test_dangerous_sql_rejected(sql, code):
    with pytest.raises(ApiError) as exc_info:
        validate_sql(sql)
    assert exc_info.value.error_code == code


def test_empty_sql_rejected():
    with pytest.raises(ApiError):
        validate_sql("   ")
