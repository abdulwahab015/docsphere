#!/usr/bin/env bash
# Builds and starts the production stack (docker-compose.yml), then checks it
# from outside, the way the load balancer and a browser reach it: the app's
# files and routes, Django behind the same origin, and the refresh cookie's
# production flags. Needs a .env (a copy of .env.example will do). Stops the
# stack and deletes its data afterwards, unless KEEP_STACK=1.
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

echo "Building and starting the stack..."
"${COMPOSE[@]}" up --detach --build
"${COMPOSE[@]}" run --rm web python manage.py migrate --noinput >/dev/null

echo "Waiting for the API through nginx..."
for _ in $(seq "$WAIT_SECONDS"); do
  [ "$(status "${VIA_HTTPS[@]}" "$BASE_URL/healthz/" || true)" = "200" ] && break
  sleep 1
done

echo
echo "The app"
app=$(headers "$BASE_URL/")
check "serves index.html" "200" "$(head -1 <<<"$app")"
check "sends a content security policy" "content-security-policy: default-src 'self'" "$app"
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
signup=$(raw_headers "${VIA_HTTPS[@]}" -X POST "$BASE_URL/api/v1/organizations/signup/" \
  -H "Content-Type: application/json" \
  -d "{\"name\": \"Smoke $(date +%s)\", \"admin_email\": \"smoke-$(date +%s)@example.com\", \"admin_password\": \"Smoke-Test-Pass-1!\"}")
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
if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed. Logs:"
  "${COMPOSE[@]}" logs --tail 50 web frontend
  exit 1
fi
echo "All checks passed."
