#!/bin/sh
# Production roles (docs/07 §4) with passwords from the environment, never from the repo.
# Runs once on an empty data volume (docker-entrypoint-initdb.d).
set -eu
: "${SAQ_APP_DB_PASSWORD:?set SAQ_APP_DB_PASSWORD}"
: "${SAQ_WORKER_DB_PASSWORD:?set SAQ_WORKER_DB_PASSWORD}"
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_pw="$SAQ_APP_DB_PASSWORD" -v worker_pw="$SAQ_WORKER_DB_PASSWORD" -v db="$POSTGRES_DB" <<'SQL'
CREATE ROLE saq_app LOGIN PASSWORD :'app_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT CONNECT ON DATABASE :"db" TO saq_app;
CREATE ROLE saq_worker LOGIN PASSWORD :'worker_pw' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS;
GRANT CONNECT ON DATABASE :"db" TO saq_worker;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SQL
