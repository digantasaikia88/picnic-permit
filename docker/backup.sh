#!/bin/sh
# Back up the Picnic Portal database (production).
#
# Run on the server, from any directory:
#     sh docker/backup.sh
#
# Writes one compressed dump per run to BACKUP_DIR and deletes dumps older
# than BACKUP_KEEP_DAYS. Schedule it daily with cron (see README.md).
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$SCRIPT_DIR")
cd "$PROJECT_DIR"

COMPOSE_FILE=${COMPOSE_FILE:-compose.prod.yaml}
BACKUP_DIR=${BACKUP_DIR:-$PROJECT_DIR/backups}
BACKUP_KEEP_DAYS=${BACKUP_KEEP_DAYS:-14}

mkdir -p "$BACKUP_DIR"

STAMP=$(date -u +%Y%m%d_%H%M%SZ)
TARGET="$BACKUP_DIR/picnic_permit_$STAMP.dump"
PARTIAL="$TARGET.partial"

echo "Backing up to $TARGET"

# pg_dump runs inside the db container with that container's own credentials.
# The custom format (-Fc) is compressed and restores with pg_restore.
if docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c 'pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom' \
    > "$PARTIAL"; then
    mv "$PARTIAL" "$TARGET"
else
    rm -f "$PARTIAL"
    echo "Backup FAILED" >&2
    exit 1
fi

if [ ! -s "$TARGET" ]; then
    echo "Backup FAILED: the dump file is empty" >&2
    exit 1
fi

# Remove old dumps.
find "$BACKUP_DIR" -name 'picnic_permit_*.dump' -type f -mtime +"$BACKUP_KEEP_DAYS" -exec rm -f {} +

echo "Backup complete: $(wc -c < "$TARGET" | tr -d " ") bytes"
