#!/usr/bin/env bash
# Runs the backend test suite against Postgres 16, the database production
# uses (CI does the same with a service container), instead of the SQLite that
# `make test` uses. Needs Docker. The database lives in memory in a throwaway
# container, removed afterwards whatever happens. Arguments go to
# `manage.py test`, e.g. a test label or `--shuffle`.
set -euo pipefail

CONTAINER=docsphere-test-postgres
PORT=${TEST_POSTGRES_PORT:-55432}
WAIT_SECONDS=60

cleanup() {
  docker rm --force "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT
# One left behind by a run that was killed outright.
cleanup

docker run --detach --name "$CONTAINER" --publish "127.0.0.1:$PORT:5432" \
  --env POSTGRES_USER=docsphere --env POSTGRES_PASSWORD=docsphere --env POSTGRES_DB=docsphere \
  --tmpfs /var/lib/postgresql/data postgres:16-alpine >/dev/null

# Over TCP: while the image initialises the database it runs a temporary
# server on the Unix socket only, then restarts.
for _ in $(seq "$WAIT_SECONDS"); do
  docker exec "$CONTAINER" pg_isready --host 127.0.0.1 --username docsphere --quiet && break
  sleep 1
done

DJANGO_SETTINGS_MODULE=core.settings.test \
  DATABASE_URL="postgres://docsphere:docsphere@127.0.0.1:$PORT/docsphere" \
  python manage.py test "$@"
