#!/bin/sh
# Restores a dump made by db-backup over the database, in one transaction:
# it either fully replaces what's there or changes nothing. Usage:
# db-restore <name of a file in $BACKUP_DIR>. Runs in the `backup` compose
# service; stop the app first (make db-restore does).
set -eu

file="${BACKUP_DIR:-/backups}/${1:?Usage: db-restore <backup file name>}"
if [ ! -f "$file" ]; then
  echo "No such backup: $file" >&2
  exit 1
fi

pg_restore --clean --if-exists --no-owner --single-transaction --dbname="$PGDATABASE" "$file"
echo "Restored $file"
