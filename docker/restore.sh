#!/bin/sh
# Restore the Picnic Portal database from a dump made by backup.sh (production).
#
#     sh docker/restore.sh backups/picnic_permit_20261119_183000Z.dump
#
# This REPLACES everything in the database with the contents of the dump.
# The backend is stopped during the restore and started again afterwards.
set -eu

if [ $# -ne 1 ]; then
    echo "Usage: sh docker/restore.sh <path to .dump file>" >&2
    exit 2
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_DIR=$(dirname -- "$SCRIPT_DIR")

case "$1" in
    /*) DUMP=$1 ;;
    *) DUMP=$(pwd)/$1 ;;
esac

if [ ! -s "$DUMP" ]; then
    echo "Dump file not found or empty: $DUMP" >&2
    exit 1
fi

cd "$PROJECT_DIR"
COMPOSE_FILE=${COMPOSE_FILE:-compose.prod.yaml}

if [ "${RESTORE_CONFIRM:-}" != "yes" ]; then
    printf 'This will REPLACE the database with %s.\nType "yes" to continue: ' "$DUMP"
    read -r ANSWER
    if [ "$ANSWER" != "yes" ]; then
        echo "Cancelled."
        exit 1
    fi
fi

echo "Stopping the backend..."
docker compose -f "$COMPOSE_FILE" stop backend

echo "Restoring..."
# --clean --if-exists drops each object before recreating it.
# --single-transaction: either the whole restore applies, or nothing changes.
docker compose -f "$COMPOSE_FILE" exec -T db \
    sh -c 'pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --clean --if-exists --no-owner --single-transaction' \
    < "$DUMP"

echo "Starting the backend (pending migrations are applied at start)..."
docker compose -f "$COMPOSE_FILE" start backend

echo "Restore complete."
