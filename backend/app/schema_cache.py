import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Connection, SchemaSnapshot
from .pg_client import extract_schema


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _snapshot_payload(snapshot: SchemaSnapshot) -> dict:
    return {
        "tables": json.loads(snapshot.schema_json),
        "truncated": snapshot.truncated,
        "token_count": snapshot.token_count,
        "generated_at": snapshot.created_at,
    }


def get_schema(
    db: Session,
    conn: Connection,
    password: str,
    refresh: bool = False,
) -> dict:
    settings = get_settings()
    now = _utcnow()

    if not refresh:
        snap = db.scalar(
            select(SchemaSnapshot)
            .where(SchemaSnapshot.connection_id == conn.id, SchemaSnapshot.expires_at > now)
            .order_by(SchemaSnapshot.created_at.desc())
            .limit(1)
        )
        if snap is not None:
            return _snapshot_payload(snap)

    tables, truncated = extract_schema(conn, password)
    schema_json = json.dumps(tables, ensure_ascii=False, separators=(",", ":"))
    token_count = len(schema_json) // 4

    db.query(SchemaSnapshot).filter(SchemaSnapshot.connection_id == conn.id).delete()
    snap = SchemaSnapshot(
        connection_id=conn.id,
        schema_json=schema_json,
        token_count=token_count,
        truncated=truncated,
        created_at=now,
        expires_at=now + timedelta(seconds=settings.SCHEMA_CACHE_TTL_SECONDS),
    )
    db.add(snap)
    db.commit()
    db.refresh(snap)
    return _snapshot_payload(snap)


def schema_for_prompt(schema_payload: dict) -> str:
    return json.dumps(schema_payload["tables"], ensure_ascii=False, separators=(",", ":"))
