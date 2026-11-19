-- Runs once on a fresh dev volume (docker-entrypoint-initdb.d). docs/07-database.md §4.
-- saq_migrator (POSTGRES_USER) owns the schema and runs Alembic.
-- saq_app is the runtime role: DML only, no DDL, never superuser, subject to row-level security.
CREATE ROLE saq_app LOGIN PASSWORD 'saq_dev_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT CONNECT ON DATABASE saq TO saq_app;
-- saq_worker is the login for system processes (outbox relay, recovery). Migration 0004 grants it
-- saq_system, which may read outbox/pipeline_state across projects (ADR-012). Still no BYPASSRLS.
CREATE ROLE saq_worker LOGIN PASSWORD 'saq_dev_password' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT CONNECT ON DATABASE saq TO saq_worker;
