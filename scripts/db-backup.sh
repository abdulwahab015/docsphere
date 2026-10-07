#!/bin/sh
# Dumps the database (pg_dump's custom format, compressed) to
# $BACKUP_DIR/docsphere-<UTC time>.dump, then deletes dumps older than
# $BACKUP_RETENTION_DAYS days. Runs in the `backup` compose service, which
# supplies the PG* connection variables. A dump is only given its final name
# once it's complete, so a failed one is never mistaken for a backup.
set -eu

dir=${BACKUP_DIR:-/backups}
name="docsphere-$(date -u +%Y%m%dT%H%M%SZ).dump"

pg_dump --format=custom --file="$dir/.$name.partial"
mv "$dir/.$name.partial" "$dir/$name"
find "$dir" -name 'docsphere-*.dump' -mtime +"$BACKUP_RETENTION_DAYS" -delete
echo "$name"
