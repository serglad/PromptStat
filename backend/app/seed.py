import re
from pathlib import Path

from cryptography.fernet import Fernet

from .config import get_settings

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def ensure_encryption_key() -> None:
    """Generate and persist a valid Fernet key if ENCRYPTION_KEY is missing/invalid.

    Keeps the prototype clone-and-run portable without weakening anything:
    the key is random, stored only in the local gitignored .env.
    """
    settings = get_settings()
    try:
        Fernet(settings.ENCRYPTION_KEY.encode())
        return
    except Exception:
        pass

    new_key = Fernet.generate_key().decode()
    if _ENV_PATH.exists():
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
        out = [f"ENCRYPTION_KEY={new_key}" if l.startswith("ENCRYPTION_KEY=") else l for l in lines]
        if not any(l.startswith("ENCRYPTION_KEY=") for l in out):
            out.append(f"ENCRYPTION_KEY={new_key}")
        _ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    else:
        _ENV_PATH.write_text(f"ENCRYPTION_KEY={new_key}\n", encoding="utf-8")

    get_settings.cache_clear()


DEMO_USER_EMAIL = "user"
DEMO_USER_PASSWORD = "user"

DEMO_CONNECTION = {
    "name": "demo",
    "db_host": "127.0.0.1",
    "db_port": 5432,
    "db_name": "demo_app",
    "db_user": "promptstat_ro",
    "db_password": "ro_pass_42",
    "ssl_mode": "disable",
}


def seed_demo(db) -> None:
    from .errors import ApiError
    from .models import Connection, User
    from .pg_client import check_connection
    from .security import encrypt_secret, hash_password

    if db.query(User).filter(User.email == DEMO_USER_EMAIL).first() is not None:
        return

    user = User(email=DEMO_USER_EMAIL, password_hash=hash_password(DEMO_USER_PASSWORD))
    db.add(user)
    db.flush()

    conn = Connection(
        user_id=user.id,
        name=DEMO_CONNECTION["name"],
        db_host=DEMO_CONNECTION["db_host"],
        db_port=DEMO_CONNECTION["db_port"],
        db_name=DEMO_CONNECTION["db_name"],
        db_user=DEMO_CONNECTION["db_user"],
        db_password_encrypted=encrypt_secret(DEMO_CONNECTION["db_password"]),
        ssl_mode=DEMO_CONNECTION["ssl_mode"],
        status="pending",
    )
    db.add(conn)
    db.commit()

    try:
        check_connection(conn, DEMO_CONNECTION["db_password"], connect_timeout=3)
        from datetime import datetime, timezone

        conn.status = "active"
        conn.last_checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
    except ApiError:
        conn.status = "inactive"
        db.commit()
