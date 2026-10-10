# Helpers and checks shared by scripts/smoke-test.sh (any deployment) and
# scripts/docker-smoke-test.sh (the local stack). Sourced, not run.
# shellcheck shell=bash

# Added by the TLS-terminating load balancer; without it Django redirects to HTTPS.
VIA_HTTPS=(-H "X-Forwarded-Proto: https")
failures=0

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

# The app's own files, as a browser loads them. Read-only.
check_app() {
  local base_url=$1 app page entry asset
  app=$(headers "$base_url/")
  check "serves index.html" "200" "$(head -1 <<<"$app")"
  check "sends a content security policy" "content-security-policy: default-src 'self'" "$app"
  check "always revalidates index.html" "cache-control: no-cache" "$app"
  page=$(curl -sS "$base_url/")
  # nginx writes the environment's settings into the page as it starts.
  check "fills in this environment's settings" '<meta name="sentry-environment" content="' \
    "$(grep -o '<meta name="sentry-environment" content="[^"][^"]*"' <<<"$page" || true)"
  check "lets the app route deep links" "200" "$(status "$base_url/projects/7")"
  entry=$(grep -o '/assets/index-[^"]*\.js' <<<"$page" | head -1)
  asset=$(headers "$base_url$entry")
  check "serves the built scripts" "content-type: application/javascript" "$asset"
  check "caches them for good" "immutable" "$asset"
  check "404s a missing asset rather than serving index.html" "404" \
    "$(status "$base_url/assets/missing.js")"
}

# Django, reached through the app's origin. Read-only.
check_django() {
  local base_url=$1
  check "answers the health check" '"status":"ok"' \
    "$(curl -sS "${VIA_HTTPS[@]}" "$base_url/healthz/")"
  check "serves the API, which asks who you are" "401" \
    "$(status "${VIA_HTTPS[@]}" "$base_url/api/v1/users/me/")"
  check "serves the admin's static files" "200" \
    "$(status "${VIA_HTTPS[@]}" "$base_url/static/admin/css/base.css")"
}
