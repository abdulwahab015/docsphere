#!/bin/sh
# Restores a backup made by db-backup: the database in one transaction (it
# either fully replaces what's there or changes nothing), then the attached
# files archived with it, replacing those in $MEDIA_DIR. Usage:
# db-restore <name of a .dump file in $BACKUP_DIR>. Runs in the `backup`
# compose service; stop the app first (make db-restore does).
set -eu

file="${BACKUP_DIR:-/backups}/${1:?Usage: db-restore <backup file name>}"
media=${MEDIA_DIR:-/media}
files="${file%.dump}.files.tar.gz"
if [ ! -f "$file" ]; then
  echo "No such backup: $file" >&2
  exit 1
fi

pg_restore --clean --if-exists --no-owner --single-transaction --dbname="$PGDATABASE" "$file"
echo "Restored $file"

# Backups from before files could be attached have no archive.
if [ -f "$files" ]; then
  find "$media" -mindepth 1 -delete
  tar -xzf "$files" -C "$media"
  echo "Restored $files"
else
  echo "No attached files were backed up with it; the current ones are kept."
fi
