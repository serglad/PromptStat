-- PromptStat example database.
-- Run as a Postgres superuser:
--   sudo -u postgres psql -f example/init_example_db.sql
--
-- Creates (idempotently):
--   role promptstat_ro / password ro_pass_42  (read-only, used by the app)
--   database demo_app with two seeded tables

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'promptstat_ro') THEN
    CREATE ROLE promptstat_ro LOGIN PASSWORD 'ro_pass_42';
  END IF;
END
$$;

SELECT 'CREATE DATABASE demo_app OWNER postgres'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'demo_app')\gexec

\connect demo_app

CREATE TABLE IF NOT EXISTS users (
  id bigserial PRIMARY KEY,
  email text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orders (
  id bigserial PRIMARY KEY,
  user_id bigint REFERENCES users (id),
  amount numeric(10, 2),
  created_at timestamptz DEFAULT now()
);

INSERT INTO users (email, created_at)
SELECT 'u' || i || '@ex.com', now() - (i || ' days')::interval
FROM generate_series(1, 200) AS i
WHERE NOT EXISTS (SELECT 1 FROM users);

INSERT INTO orders (user_id, amount, created_at)
SELECT (random() * 199)::int + 1,
       (random() * 100)::numeric,
       now() - (floor(random() * 90) || ' days')::interval
FROM generate_series(1, 800)
WHERE NOT EXISTS (SELECT 1 FROM orders);

GRANT USAGE ON SCHEMA public TO promptstat_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO promptstat_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO promptstat_ro;
