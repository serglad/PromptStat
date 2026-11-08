import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("email")
    @classmethod
    def _email_format(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("email is not valid")
        return v


class RegisterResponse(BaseModel):
    user_id: str
    token: str


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str


class ConnectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(ge=1, le=65535)
    db_name: str = Field(min_length=1, max_length=255)
    db_user: str = Field(min_length=1, max_length=255)
    db_password: str = Field(min_length=1, max_length=1024)
    ssl_mode: str | None = None

    @field_validator("ssl_mode")
    @classmethod
    def _ssl_mode_allowed(cls, v: str | None) -> str | None:
        allowed = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
        if v is not None and v not in allowed:
            raise ValueError("ssl_mode is not valid")
        return v


class ConnectionOut(BaseModel):
    id: str
    name: str
    host: str
    port: int
    db_name: str
    db_user: str
    ssl_mode: str | None
    status: str
    last_checked_at: datetime | None
    created_at: datetime


class SchemaColumnOut(BaseModel):
    name: str
    type: str
    nullable: bool
    is_pk: bool = False
    fk_target: str | None = None


class SchemaTableOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_name: str = Field(alias="schema")
    table: str
    columns: list[SchemaColumnOut]


class SchemaResponse(BaseModel):
    tables: list[SchemaTableOut]
    truncated: bool
    token_count: int
    generated_at: datetime


class QueryRequest(BaseModel):
    connection_id: str
    prompt: str = Field(min_length=1)
    conversation_id: str | None = None

    @field_validator("connection_id")
    @classmethod
    def _valid_uuid(cls, v: str) -> str:
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("connection_id must be a UUID")
        return v


class QueryResponse(BaseModel):
    sql: str
    columns: list[str]
    data: list[list]
    row_count: int
    truncated: bool
    chart_type: str
    chart_spec: dict | None
    duration_ms: int
    conversation_id: str


class HistoryItem(BaseModel):
    id: str
    connection_id: str
    prompt_text: str
    generated_sql: str | None
    execution_status: str
    error_code: str | None
    duration_ms: int | None
    row_count: int | None
    truncated: bool | None
    chart_type: str | None
    created_at: datetime
