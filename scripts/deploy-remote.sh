#!/usr/bin/env bash
# Deploys a release to a server over SSH: copies what the server needs to run
# it (the compose file and the server-side scripts - the images hold the code)
# into PATH, then runs scripts/deploy.sh there. Used by the Deploy workflow;
# SSH's own configuration (key, known hosts) decides how it connects.
#
# Usage: scripts/deploy-remote.sh USER@HOST PATH TAG [REGISTRY_USER]
# A registry token on stdin is passed through to scripts/deploy.sh.
set -euo pipefail

target=${1:?"Usage: $0 <user@host> <path on the server> <release tag> [registry user]"}
path=${2:?"Usage: $0 <user@host> <path on the server> <release tag> [registry user]"}
tag=${3:?"Usage: $0 <user@host> <path on the server> <release tag> [registry user]"}
registry_user=${4:-}

cd "$(dirname "$0")/.."

# Expanded here, on purpose: quoted for the server's shell with %q.
remote_path=$(printf '%q' "$path")
# shellcheck disable=SC2029
tar --no-xattrs -czf - docker-compose.yml Makefile scripts/deploy.sh scripts/db-backup.sh scripts/db-restore.sh |
  ssh "$target" "mkdir -p $remote_path && tar -xzf - -C $remote_path"
# shellcheck disable=SC2029
ssh "$target" "cd $remote_path && ./scripts/deploy.sh $(printf '%q %q' "$tag" "$registry_user")"
