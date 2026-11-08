from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    INTERNAL_DATABASE_URL: str = "sqlite:///./promptstat.db"
    ENCRYPTION_KEY: str = "CHANGE_ME_generate_with_cryptography_Fernet"
    JWT_SECRET: str = "CHANGE_ME_jwt_secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_TTL_MINUTES: int = 1440

    LLM_PROVIDER: str = "openai"
    LLM_API_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TIMEOUT_SECONDS: float = 45.0
    LLM_MAX_TOKENS: int = 1024

    SCHEMA_MAX_TOKENS: int = 10000
    DEFAULT_ROW_LIMIT: int = 1000
    STATEMENT_TIMEOUT_MS: int = 30000
    LOCK_TIMEOUT_MS: int = 5000
    IDLE_IN_TRANSACTION_TIMEOUT_MS: int = 30000
    SCHEMA_CACHE_TTL_SECONDS: int = 3600
    MAX_CONCURRENT_QUERIES_PER_CONNECTION: int = 2
    RATE_LIMIT_PER_MINUTE: int = 10

    MAX_PROMPT_LENGTH: int = 2000


@lru_cache
def get_settings() -> Settings:
    return Settings()
