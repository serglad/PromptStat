# PromptStat (MVP-прототип)

Задавайте вопросы на русском о живой базе PostgreSQL и получайте таблицу, график и сгенерированный SQL.

**Объём MVP (жёстко верифицирован):** подключение к Postgres + съём схемы · промпт → SQL → таблица · автографик + показ SQL. Ничего больше.

## Стек

- Backend: Python 3.12, FastAPI, SQLAlchemy, SQLite (внутренняя БД метаданных)
- Frontend: React 18 + Vite + Chart.js
- LLM: любой OpenAI-совместимый API (`LLM_API_URL` / `LLM_API_KEY` / `LLM_MODEL`)
- Безопасность SQL: разбор pglast (libpg_query) → только единственный SELECT/WITH-SELECT, функции из denylist запрещены, read-only транзакция, таймауты, лимит строк
- Доступ к клиентской Postgres: обязательна read-only роль

## Структура

```
backend/    FastAPI-приложение + тесты (run_tests.sh)
frontend/   React SPA (Vite); продакшен-сборку отдаёт сам FastAPI
.env.example  все переменные конфигурации
```

## Пример базы + демо-пользователь

`example/init_example_db.sql` создаёт наполненную демо-базу Postgres (`demo_app`:
users/orders) и read-only роль `promptstat_ro` / `ro_pass_42`:

```bash
sudo -u postgres psql -f example/init_example_db.sql
```

При запуске backend создаёт демо-аккаунт — логин `user`, пароль `user` —
с преднастроенным подключением к `demo_app` (статус `active`, если пример БД
существует, иначе `inactive`; исправьте или удалите его в интерфейсе). `ENCRYPTION_KEY`
автоматически генерируется в `backend/.env` при первом запуске, если не настроена.

## Локальный запуск (разработка)

Backend:

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp ../.env.example .env        # затем заполните ENCRYPTION_KEY, JWT_SECRET, значения LLM_*
# сгенерировать ключи:
#   .venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

Frontend (dev, с прокси API):

```bash
cd frontend
npm install
npm run dev                    # http://localhost:5173
```

## Запуск одним сервисом (продакшен-режим, один порт)

```bash
cd frontend && npm run build && cd ..
cd backend && .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

FastAPI отдаёт собранную SPA из `frontend/dist` плюс API на `/api/*`.
Этой одной команды достаточно для VPS (поставьте перед ней nginx/Caddy для TLS).

## Тесты

```bash
cd backend && ./run_tests.sh          # 46 тестов, без сети, Postgres не требуется
```

## Примечания по безопасности

- Пароли подключений шифруются Fernet (`ENCRYPTION_KEY`), никогда не возвращаются API и не попадают в логи.
- Выполняется ровно один SQL-запрос, только SELECT / WITH…SELECT; DML, DDL, COPY, CALL, DO, SET, блокирующие конструкции, SELECT INTO, изменяющие CTE и опасные функции (`pg_sleep`, `dblink`, `lo_import`, `pg_read_file`, …) отклоняются.
- Запросы выполняются в транзакциях `READ ONLY` с `statement_timeout` (30 с), `lock_timeout`, `idle_in_transaction_session_timeout` и лимитом строк (по умолчанию 1000; сверх лимита → `truncated: true`).
- В LLM отправляются схема + вопрос (+ предыдущий вопрос/SQL в диалоге) — никогда сырые строки данных.
- История запросов хранит только метаданные; строки результатов живут в памяти только на время запроса.

## Конфигурация

См. `.env.example` — каждая настройка является переменной окружения (провайдер/URL/модель/таймауты LLM, бюджет токенов схемы, лимит строк, таймауты БД, TTL кэша, rate limits).

## Вне объёма (осознанно)

Другие СУБД, конструктор дашбордов, SSO, запись в базу, биллинг, алерты, собственные модели, on-prem-упаковка, очереди/воркеры.
