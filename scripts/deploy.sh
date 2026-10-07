#!/usr/bin/env bash
# Deploys a release on this server: pulls the images the Release workflow
# published for TAG (the git commit they were built from), takes a backup,
# records TAG in .env and restarts the stack on the new images - the `migrate`
# service applies any migrations before Django starts - then waits until
# every service is healthy. Rolling back is deploying an earlier TAG.
#
# Runs in the directory holding docker-compose.yml and .env (the Deploy
# workflow copies this script there with scripts/deploy-remote.sh). .env names
# the images: BACKEND_IMAGE and FRONTEND_IMAGE.
#
# Usage: scripts/deploy.sh TAG [REGISTRY_USER]
# With REGISTRY_USER, a registry token is read from stdin and used for this
# pull only; without it, the server's own registry login (if any) is used.
set -euo pipefail

tag=${1:?"Usage: $0 <release tag, e.g. a git commit SHA> [registry user]"}
registry_user=${2:-}
# Waiting for every service to be healthy: migrations run first.
WAIT_SECONDS=300

cd "$(dirname "$0")/.."

if [[ ! "$tag" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  echo "Not a valid image tag: $tag" >&2
  exit 1
fi

backend_image=$(sed -n 's/^BACKEND_IMAGE=//p' .env)
frontend_image=$(sed -n 's/^FRONTEND_IMAGE=//p' .env)
if [ -z "$backend_image" ] || [ -z "$frontend_image" ]; then
  echo "Set BACKEND_IMAGE and FRONTEND_IMAGE in .env to the images to run." >&2
  exit 1
fi

if [ -n "$registry_user" ]; then
  registry=${backend_image%%/*}
  docker login "$registry" --username "$registry_user" --password-stdin >/dev/null
  trap 'docker logout "$registry" >/dev/null' EXIT
fi

echo "Pulling release $tag..."
# Before anything changes, so a release that isn't there stops the deploy.
IMAGE_TAG=$tag docker compose pull --quiet web frontend

if docker compose ps --status running --services | grep -qx backup; then
  echo "Backing up the database..."
  docker compose exec -T backup sh /usr/local/bin/db-backup
fi

# In .env, so every later `docker compose` command here uses this release too.
# Rewritten in place, keeping the file's owner and permissions.
env_file=$(grep -v '^IMAGE_TAG=' .env)
printf '%s\nIMAGE_TAG=%s\n' "$env_file" "$tag" >.env

echo "Starting release $tag..."
if ! docker compose up --detach --no-build --remove-orphans --wait --wait-timeout "$WAIT_SECONDS"; then
  docker compose ps --all
  docker compose logs --tail 50 migrate web frontend
  echo "Release $tag did not become healthy. Roll back by deploying the previous release." >&2
  exit 1
fi

for service in web frontend; do
  running=$(docker compose ps --format '{{.Image}}' "$service")
  if [[ "$running" != *":$tag" ]]; then
    echo "$service is running $running, not release $tag." >&2
    exit 1
  fi
done

# Releases no container uses any more and older than two weeks; any of them
# can be pulled from the registry again to roll back.
docker image prune --all --force --filter "until=336h" >/dev/null
echo "Release $tag is running."
