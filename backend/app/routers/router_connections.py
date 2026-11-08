from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user
from ..errors import ApiError
from ..models import Connection, User
from ..pg_client import check_connection, extract_schema
from ..schemas import ConnectionCreateRequest, ConnectionOut, SchemaResponse
from ..security import decrypt_secret, encrypt_secret

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


def _to_out(conn: Connection) -> ConnectionOut:
    return ConnectionOut(
        id=conn.id,
        name=conn.name,
        host=conn.db_host,
        port=conn.db_port,
        db_name=conn.db_name,
        db_user=conn.db_user,
        ssl_mode=conn.ssl_mode,
        status=conn.status,
        last_checked_at=conn.last_checked_at,
        created_at=conn.created_at,
    )


def get_owned_connection(db: Session, user: User, connection_id: str) -> Connection:
    conn = db.get(Connection, connection_id)
    if conn is None or conn.user_id != user.id:
        raise ApiError(404, "CONNECTION_NOT_FOUND", "Подключение не найдено.")
    return conn


@router.post("", response_model=ConnectionOut)
def create_connection(
    body: ConnectionCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conn = Connection(
        user_id=user.id,
        name=body.name,
        db_host=body.host,
        db_port=body.port,
        db_name=body.db_name,
        db_user=body.db_user,
        db_password_encrypted=encrypt_secret(body.db_password),
        ssl_mode=body.ssl_mode,
        status="pending",
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)

    password = decrypt_secret(conn.db_password_encrypted)
    check_connection(conn, password)
    extract_schema(conn, password)

    conn.status = "active"
    conn.last_checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(conn)
    return _to_out(conn)


@router.get("", response_model=list[ConnectionOut])
def list_connections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conns = db.scalars(
        select(Connection).where(Connection.user_id == user.id).order_by(Connection.created_at)
    ).all()
    return [_to_out(c) for c in conns]


@router.get("/{connection_id}/schema", response_model=SchemaResponse)
def get_schema(
    connection_id: str,
    refresh: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..schema_cache import get_schema as get_schema_cached

    conn = get_owned_connection(db, user, connection_id)
    password = decrypt_secret(conn.db_password_encrypted)
    payload = get_schema_cached(db, conn, password, refresh=refresh)
    return SchemaResponse(
        tables=payload["tables"],
        truncated=payload["truncated"],
        token_count=payload["token_count"],
        generated_at=payload["generated_at"],
    )
