#!/bin/sh
# Dumps the database (pg_dump's custom format, compressed) to
# $BACKUP_DIR/docsphere-<UTC time>.dump and archives the attached files in
# $MEDIA_DIR beside it as docsphere-<UTC time>.files.tar.gz, then deletes
# backups older than $BACKUP_RETENTION_DAYS days. Runs in the `backup` compose
# service, which supplies the PG* connection variables. Each file is only
# given its final name once it's complete, so a failed one is never mistaken
# for a backup. Prints the dump's name last.
set -eu

dir=${BACKUP_DIR:-/backups}
media=${MEDIA_DIR:-/media}
stamp="docsphere-$(date -u +%Y%m%dT%H%M%SZ)"

pg_dump --format=custom --file="$dir/.$stamp.dump.partial"
tar -czf "$dir/.$stamp.files.tar.gz.partial" -C "$media" .
mv "$dir/.$stamp.files.tar.gz.partial" "$dir/$stamp.files.tar.gz"
mv "$dir/.$stamp.dump.partial" "$dir/$stamp.dump"
find "$dir" \( -name 'docsphere-*.dump' -o -name 'docsphere-*.files.tar.gz' \) \
  -mtime +"$BACKUP_RETENTION_DAYS" -delete
echo "$stamp.dump"
