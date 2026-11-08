import time
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..chart import build_chart
from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user
from ..errors import ApiError
from ..llm import CannotGenerateError, LlmUnavailableError, build_prompt, call_llm, extract_sql
from ..models import QueryHistory, User
from ..pg_client import run_read_only_query
from ..ratelimit import ConnectionSemaphoreRegistry, rate_limiter
from ..routers.router_connections import get_owned_connection
from ..schemas import HistoryItem, QueryRequest, QueryResponse
from ..schema_cache import get_schema, schema_for_prompt
from ..security import decrypt_secret
from ..sql_guard import validate_sql

router = APIRouter(prefix="/api/v1", tags=["query"])

_semaphores: ConnectionSemaphoreRegistry | None = None


def _get_semaphores() -> ConnectionSemaphoreRegistry:
    global _semaphores
    if _semaphores is None:
        _semaphores = ConnectionSemaphoreRegistry(get_settings().MAX_CONCURRENT_QUERIES_PER_CONNECTION)
    return _semaphores


@router.post("/query", response_model=QueryResponse)
def run_query(
    body: QueryRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    settings = get_settings()

    if not body.prompt or not body.prompt.strip():
        raise ApiError(400, "VALIDATION_ERROR", "Вопрос не может быть пустым.")
    if len(body.prompt) > settings.MAX_PROMPT_LENGTH:
        raise ApiError(400, "VALIDATION_ERROR", f"Вопрос длиннее {settings.MAX_PROMPT_LENGTH} символов.")

    if not rate_limiter.allow(user.id, settings.RATE_LIMIT_PER_MINUTE):
        raise ApiError(429, "RATE_LIMITED", "Слишком много запросов, подождите минуту.")
    if user.monthly_query_limit is not None and user.monthly_query_count >= user.monthly_query_limit:
        raise ApiError(429, "RATE_LIMITED", "Месячный лимит запросов исчерпан.")

    conn = get_owned_connection(db, user, body.connection_id)
    conversation_id = body.conversation_id or str(uuid.uuid4())
    started = time.monotonic()

    def history(status: str, sql: str | None = None, error_code: str | None = None,
                row_count: int | None = None, truncated: bool | None = None,
                chart_type: str | None = None) -> None:
        db.add(QueryHistory(
            user_id=user.id,
            connection_id=conn.id,
            conversation_id=conversation_id,
            prompt_text=body.prompt,
            generated_sql=sql,
            execution_status=status,
            error_code=error_code,
            duration_ms=int((time.monotonic() - started) * 1000),
            row_count=row_count,
            truncated=truncated,
            chart_type=chart_type,
        ))
        db.commit()

    password = decrypt_secret(conn.db_password_encrypted)
    try:
        schema_payload = get_schema(db, conn, password)
    except ApiError as exc:
        history("error", error_code=exc.error_code)
        raise
    schema_json = schema_for_prompt(schema_payload)

    history_rows = db.scalars(
        select(QueryHistory)
        .where(
            QueryHistory.conversation_id == conversation_id,
            QueryHistory.execution_status == "success",
        )
        .order_by(QueryHistory.created_at.desc())
        .limit(3)
    ).all()
    prompt = build_prompt(
        schema_json, body.prompt,
        [(h.prompt_text, h.generated_sql or "") for h in reversed(history_rows)],
    )

    try:
        llm_answer = call_llm(prompt)
        sql = extract_sql(llm_answer)
    except (CannotGenerateError, LlmUnavailableError) as exc:
        history("llm_error", error_code=getattr(exc, "error_code", "LLM_UNAVAILABLE"))
        raise

    try:
        sql = validate_sql(sql)
    except ApiError as exc:
        history("rejected", error_code=exc.error_code)
        raise

    sem = _get_semaphores().get(conn.id)
    if not sem.acquire(blocking=False):
        history("rejected", sql=sql, error_code="CONCURRENCY_LIMIT")
        raise ApiError(429, "RATE_LIMITED", "По этому подключению уже выполняется максимум запросов.")
    try:
        result = run_read_only_query(conn, password, sql)
    except ApiError as exc:
        history("error", sql=sql, error_code=exc.error_code)
        raise
    finally:
        sem.release()

    chart_type, chart_spec = build_chart(result.columns, result.rows, None)
    duration_ms = int((time.monotonic() - started) * 1000)
    history("success", sql=sql, row_count=len(result.rows), truncated=result.truncated, chart_type=chart_type)

    user.monthly_query_count = (user.monthly_query_count or 0) + 1
    db.commit()

    return QueryResponse(
        sql=sql,
        columns=result.columns,
        data=result.rows,
        row_count=len(result.rows),
        truncated=result.truncated,
        chart_type=chart_type,
        chart_spec=chart_spec,
        duration_ms=duration_ms,
        conversation_id=conversation_id,
    )


@router.get("/history", response_model=list[HistoryItem])
def get_history(
    connection_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(QueryHistory).where(QueryHistory.user_id == user.id)
    if connection_id:
        conn = get_owned_connection(db, user, connection_id)
        stmt = stmt.where(QueryHistory.connection_id == conn.id)
    items = db.scalars(stmt.order_by(QueryHistory.created_at.desc()).limit(100)).all()
    return [
        HistoryItem(
            id=h.id,
            connection_id=h.connection_id,
            prompt_text=h.prompt_text,
            generated_sql=h.generated_sql,
            execution_status=h.execution_status,
            error_code=h.error_code,
            duration_ms=h.duration_ms,
            row_count=h.row_count,
            truncated=h.truncated,
            chart_type=h.chart_type,
            created_at=h.created_at,
        )
        for h in items
    ]
