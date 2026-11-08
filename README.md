# PromptStat (MVP prototype)

Ask questions in Russian about a live PostgreSQL database, get a table, a chart, and the generated SQL.

**MVP scope (hard-verified):** Postgres connection + schema extraction · prompt → SQL → table · auto chart + SQL display. Nothing else.

## Stack

- Backend: Python 3.12, FastAPI, SQLAlchemy, SQLite (internal metadata DB)
- Frontend: React 18 + Vite + Chart.js
- LLM: any OpenAI-compatible API (`LLM_API_URL` / `LLM_API_KEY` / `LLM_MODEL`)
- SQL safety: pglast (libpg_query) parse → single SELECT/WITH-SELECT only, denylisted functions, read-only transaction, timeouts, row limit
- Client Postgres access: read-only role required

## Layout

```
backend/    FastAPI app + tests (run_tests.sh)
frontend/   React SPA (Vite); production build served by FastAPI itself
.env.example  all configuration variables
```

## Example database + demo user

`example/init_example_db.sql` creates a seeded Postgres demo DB (`demo_app`:
users/orders) and a read-only role `promptstat_ro` / `ro_pass_42`:

```bash
sudo -u postgres psql -f example/init_example_db.sql
```

On startup the backend seeds a demo account — login `user`, password `user` —
with a connection to `demo_app` preconfigured (status `active` if the example
DB exists, otherwise `inactive`; fix or delete it in the UI). `ENCRYPTION_KEY`
is auto-generated into `backend/.env` on first start if not configured.

## Run locally (development)

Backend:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp ../.env.example .env        # then fill in ENCRYPTION_KEY, JWT_SECRET, LLM_* values
# generate keys:
#   .venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Frontend (dev, with API proxy):

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

## Run as one service (production-like, single port)

```bash
cd frontend && npm run build && cd ..
cd backend && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

FastAPI serves the built SPA from `frontend/dist` plus the API on `/api/*`.
That single command is all a VPS needs (put it behind nginx/Caddy for TLS).

## Tests

```bash
cd backend && ./run_tests.sh          # 46 tests, no network, no Postgres needed
```

## Security notes

- Connection passwords are Fernet-encrypted (`ENCRYPTION_KEY`), never returned by the API, never logged.
- Only one SQL statement is executed, only SELECT / WITH…SELECT; DML, DDL, COPY, CALL, DO, SET, locking clauses, SELECT INTO, data-modifying CTEs and dangerous functions (`pg_sleep`, `dblink`, `lo_import`, `pg_read_file`, …) are rejected.
- Queries run in `READ ONLY` transactions with `statement_timeout` (30 s), `lock_timeout`, `idle_in_transaction_session_timeout`, and a row limit (default 1000; excess → `truncated: true`).
- The LLM receives schema + question (+ previous question/SQL in a conversation) — never raw data rows.
- Query history stores metadata only; result rows live in memory during the request only.

## Config

See `.env.example` — every knob is an env var (LLM provider/URL/model/timeouts, schema token budget, row limit, DB timeouts, cache TTL, rate limits).

## Out of scope (deliberately)

Other DBs, dashboard builder, SSO, write access, billing, alerts, custom models, on-prem packaging, queues/workers.
