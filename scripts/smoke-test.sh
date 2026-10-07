#!/usr/bin/env bash
# Checks a running DocSphere from outside, the way a browser reaches it: the
# app's files and headers, and Django behind the same origin. Read-only, so it
# is safe to run against production; the Deploy workflow runs it after every
# deploy, and `make docker-smoke` runs it against the local stack.
# Usage: scripts/smoke-test.sh https://docsphere.example.com
set -euo pipefail

base_url=${1:?"Usage: $0 <the app's URL, e.g. https://docsphere.example.com>"}
base_url=${base_url%/}

# shellcheck source=scripts/lib/smoke.sh
source "$(dirname "$0")/lib/smoke.sh"

echo "Checking $base_url"
echo
echo "The app"
check_app "$base_url"
echo
echo "Django, behind the same origin"
check_django "$base_url"

echo
if [ "$failures" -gt 0 ]; then
  echo "$failures check(s) failed."
  exit 1
fi
echo "All checks passed."
