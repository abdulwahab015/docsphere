#!/usr/bin/env bash
# Builds and starts the production stack (docker-compose.yml), then checks it
# from outside, the way the load balancer and a browser reach it: every
# service healthy with no manual step, the app's files and routes, Django
# behind the same origin, the refresh cookie's production flags, scheduled
# tasks reaching the worker, and a backup -> change -> restore round trip.
# Needs a .env (a copy of .env.example will do). Stops the stack and deletes
# its data afterwards, unless KEEP_STACK=1.
set -euo pipefail

BASE_URL="http://localhost:${APP_PORT:-8080}"
# Added by the TLS-terminating load balancer; without it Django redirects to HTTPS.
VIA_HTTPS=(-H "X-Forwarded-Proto: https")
# A project name of its own, so its containers and volumes (which it deletes
# afterwards) are never the dev stack's.
COMPOSE=(docker compose --project-name docsphere-smoke -f docker-compose.yml)
WAIT_SECONDS=90
failures=0

cleanup() {
  if [ "${KEEP_STACK:-0}" != "1" ]; then
    "${COMPOSE[@]}" down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

check() {
  local description=$1 expected=$2 actual=$3
  if [[ "$actual" == *"$expected"* ]]; then
    echo "ok    $description"
  else
    echo "FAIL  $description: expected '$expected', got '$actual'"
    failures=$((failures + 1))
  fi
}

# The status line and headers of a response.
raw_headers() {
  curl -sS -o /dev/null -D - "$@" | tr -d '\r'
}

# The same, lower-cased for matching names and flags.
headers() {
  raw_headers "$@" | tr '[:upper:]' '[:lower:]'
}

status() {
  curl -sS -o /dev/null -w '%{http_code}' "$@"
}

# The first line of a service's logs containing the given text, waiting for it
# to appear; empty if it doesn't in time.
log_line() {
  local service=$1 text=$2 line
  for _ in $(seq "$WAIT_SECONDS"); do
    line=$("${COMPOSE[@]}" logs --no-log-prefix "$service" 2>/dev/null | grep -F -- "$text" | head -1 || true)
    if [ -n "$line" ]; then
      echo "$line"
      return
    fi
    sleep 1
  done
}

# Waits until Django answers through nginx.
wait_for_api() {
  for _ in $(seq "$WAIT_SECONDS"); do
    [ "$(status "${VIA_HTTPS[@]}" "$BASE_URL/healthz/" || true)" = "200" ] && return
    sleep 1
  done
}

# How many organizations the database holds.
organization_count() {
  "${COMPOSE[@]}" exec -T db sh -c \
    'psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --tuples-only --no-align --command "SELECT count(*) FROM organizations_organization"'
}

# Signs up a new organization through nginx; prints the response's status
# line and headers.
sign_up() {
  local who="$1-$(date +%s)"
  raw_headers "${VIA_HTTPS[@]}" -X POST "$BASE_URL/api/v1/organizations/signup/" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"Smoke $who\", \"admin_email\": \"$who@example.com\", \"admin_password\": \"Smoke-Test-Pass-1!\"}"
}

echo "Building and starting the stack (it migrates itself)..."
"${COMPOSE[@]}" up --detach --build

echo "Waiting for the API through nginx..."
wait_for_api

echo
echo "The stack"
# A service reads "starting" until its first health check has passed.
for _ in $(seq "$WAIT_SECONDS"); do
  health=$("${COMPOSE[@]}" ps --format '{{.Service}}={{.Health}}')
  [ "$(grep -c '=healthy$' <<<"$health")" -ge 4 ] && break
  sleep 1
done
for service in db redis web frontend; do
  check "$service is healthy" "$service=healthy" "$(grep "^$service=" <<<"$health" || true)"
done
check "the migrations ran, then the service exited cleanly" "migrate=exited (0)" \
  "$("${COMPOSE[@]}" ps --all --format '{{.Service}}={{.State}} ({{.ExitCode}})' | grep '^migrate=' || true)"

echo
echo "The app"
app=$(headers "$BASE_URL/")
check "serves index.html" "200" "$(head -1 <<<"$app")"
check "sends a content security policy" "content-security-policy: default-src 'self'" "$app"
# Bracketed, so the check is for exactly this - no other origin allowed.
check "...whose requests go only to this origin" "[connect-src 'self']" \
  "[$(grep -o "connect-src [^;]*" <<<"$app" | sed 's/ *$//')]"
# The error-reporting origin, once configured, is added to it at start-up.
ingest=https://o1.ingest.example.com
check "...and to the error-reporting origin when one is set" "[connect-src 'self' $ingest]" \
  "[$("${COMPOSE[@]}" run --rm --no-deps -e SENTRY_INGEST_ORIGIN="$ingest" frontend nginx -T 2>/dev/null |
    grep -o "connect-src [^;]*" | head -1 | sed 's/ *$//')]"
check "always revalidates index.html" "cache-control: no-cache" "$app"
check "lets the app route deep links" "200" "$(status "$BASE_URL/projects/7")"
entry=$(curl -sS "$BASE_URL/" | grep -o '/assets/index-[^"]*\.js' | head -1)
asset=$(headers "$BASE_URL$entry")
check "serves the built scripts" "content-type: application/javascript" "$asset"
check "caches them for good" "immutable" "$asset"
check "404s a missing asset rather than serving index.html" "404" \
  "$(status "$BASE_URL/assets/missing.js")"

echo
echo "Django, behind the same origin"
check "answers the health check" '"status":"ok"' \
  "$(curl -sS "${VIA_HTTPS[@]}" "$BASE_URL/healthz/")"
check "redirects plain HTTP to HTTPS" "location: https://" "$(headers "$BASE_URL/healthz/")"
check "serves the admin" "302" "$(status "${VIA_HTTPS[@]}" "$BASE_URL/${DJANGO_ADMIN_PATH:-admin/}")"
check "serves the admin's static files" "200" \
  "$(status "${VIA_HTTPS[@]}" "$BASE_URL/static/admin/css/base.css")"

echo
echo "Signing up through the API"
signup=$(sign_up smoke)
check "creates the organization" "201" "$(head -1 <<<"$signup")"
cookie=$(grep -i '^set-cookie: refresh_token=' <<<"$signup" || true)
flags=$(tr '[:upper:]' '[:lower:]' <<<"$cookie")
check "sets the refresh cookie HttpOnly" "httponly" "$flags"
check "...Secure" "secure" "$flags"
check "...SameSite=Lax" "samesite=lax" "$flags"
check "...only for the auth endpoints" "path=/api/v1/users/auth/" "$flags"
# curl only sends a Secure cookie over HTTPS, so pass it on by hand, as the
# browser does over the real HTTPS origin.
refresh_token=$(grep -o 'refresh_token=[^;]*' <<<"$cookie" | head -1)
check "refreshes the session from the cookie" "200" \
  "$(status "${VIA_HTTPS[@]}" -X POST "$BASE_URL/api/v1/users/auth/refresh/" \
    -H "Content-Type: application/json" -H "Cookie: $refresh_token" -d '{}')"

echo
echo "Background tasks"
running=$("${COMPOSE[@]}" ps --status running --services)
check "runs one scheduler (beat)" "1" "$(grep -cx beat <<<"$running" || true)"
check "...which has started" "beat: Starting" "$(log_line beat "beat: Starting")"
# Sent through the broker the way beat sends it at midnight, so this proves
# the wiring without waiting for the schedule.
reminder_task=subscriptions.tasks.send_expiry_reminders_task
task_id=$("${COMPOSE[@]}" exec -T beat celery -A core call "$reminder_task" | tr -d '\r')
check "the worker runs the renewal reminders" "succeeded" \
  "$(log_line worker "$reminder_task[$task_id] succeeded")"

echo
echo "Backups"
check "the backup service made one when it started" "docsphere-" \
  "$(log_line backup "docsphere-")"
before=$(organization_count)
backup=$("${COMPOSE[@]}" exec -T backup sh /usr/local/bin/db-backup | tail -1 | tr -d '\r')
check "takes one on request" ".dump" "$backup"
sign_up after-backup >/dev/null
check "...after which a new organization is there" "$((before + 1))" "$(organization_count)"
"${COMPOSE[@]}" stop web worker beat flower >/dev/null 2>&1
"${COMPOSE[@]}" exec -T backup sh /usr/local/bin/db-restore "$backup" >/dev/null
"${COMPOSE[@]}" start web worker beat flower >/dev/null 2>&1
check "restoring it brings back the database as it was" "$before" "$(organization_count)"
wait_for_api
# The restarted web container has a new address, which nginx must follow.
check "...and the app answers again through nginx" "200" \
  "$(status "${VIA_HTTPS[@]}" "$BASE_URL/healthz/")"

echo
if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed. Logs:"
  "${COMPOSE[@]}" logs --tail 50 migrate web frontend worker beat backup
  exit 1
fi
echo "All checks passed."
