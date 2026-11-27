#!/bin/sh
# Nightly logical backup of the control-plane database (docs/24 §backups).
# Evidence and reports live in your S3 bucket: enable versioning + lifecycle there.
#   deploy/scripts/backup.sh [backup-dir]      (keeps the newest $KEEP dumps, default 14)
set -eu
DIR="${1:-./backups}"
KEEP="${KEEP:-14}"
COMPOSE="docker compose -f deploy/compose.prod.yml --env-file .env.production"
mkdir -p "$DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
$COMPOSE exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$DIR/saq-$STAMP.dump"
test -s "$DIR/saq-$STAMP.dump"
ls -1t "$DIR"/saq-*.dump | tail -n +"$((KEEP + 1))" | xargs -r rm --
echo "backup written: $DIR/saq-$STAMP.dump"
# Restore (into an empty database):
#   $COMPOSE exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < dump
