# DocSphere

Organizations store, manage and share documents among their members, with access sold as a
Stripe subscription. A Django REST API and a React app.

**Working on it:** [CONTRIBUTING.md](CONTRIBUTING.md) covers running it locally, the tests,
demo accounts, Stripe test mode, and the rules the code follows.

## Deploying

`docker-compose.yml` is the production stack:

| Service | What it is |
| --- | --- |
| `frontend` | nginx: serves the built app and forwards Django's paths to `web`. The only published port (`APP_PORT`, default 8080). |
| `web` | Django on gunicorn (`core.settings.production`), reachable only inside the stack. Files attached to documents are stored on its `media` volume. |
| `worker`, `flower` | Celery worker, and its dashboard |
| `beat` | Sends scheduled tasks (the daily renewal reminders) to the worker. Run exactly one. |
| `db`, `redis` | Postgres, and the Celery broker |
| `migrate` | Applies the database migrations at every start, then exits; the Django services wait for it |
| `backup` | Dumps the database, and archives the attached files with it, daily into the `db_backups` volume; keeps 14 days |

Every long-running service has a health check (`docker compose ps` shows it), and each
waits for what it needs to be healthy before starting.

The browser sees **one origin**: nginx serves the app and sends `/api/`, `/static/`,
`/stripe/` (Stripe's webhook), `/healthz/` and the admin (`DJANGO_ADMIN_PATH`) to Django.
The app calls the API at a relative `/api/v1`, so the same image works in any environment,
and the refresh-token cookie is first-party (`Secure`, `HttpOnly`, `SameSite=Lax`).

TLS ends at a load balancer in front of `APP_PORT`. It must send `X-Forwarded-Proto: https`
(Django redirects anything else to HTTPS) and `X-Forwarded-For`; nginx passes both through
unchanged.

1. Copy `.env.example` to `.env` and fill it in. For the public origin, e.g.
   `https://docsphere.example.com`: set `FRONTEND_URL` and `CORS_ALLOWED_ORIGINS` to it and
   `ALLOWED_HOSTS` to its hostname. Set `DJANGO_ADMIN_PATH` to something hard to guess.
   Set `STRIPE_PRODUCT_ID` to the Stripe product whose recurring prices are your plans.
2. Start the stack: deployed by the release pipeline (below), or built from a checkout
   with `docker compose up -d --build`. Migrations run on their own, before Django starts.
3. In the Django admin, add a dj-stripe **Webhook endpoint** for `https://<your host>`.
   dj-stripe registers it with Stripe, which then calls `/stripe/webhook/<uuid>/`.

### Releases

Every merge to `main` is a release (`.github/workflows/release.yml`):

1. Both images are built and published to GitHub's container registry, tagged with the
   commit they were built from: `ghcr.io/<owner>/docsphere-backend:<sha>` and
   `ghcr.io/<owner>/docsphere-frontend:<sha>`. Error reports name that commit.
2. They're deployed to **staging** (`.github/workflows/deploy.yml`): the release's compose
   file and server scripts are copied to the server over SSH, and `scripts/deploy.sh <sha>`
   pulls the images, backs up the database, restarts the stack on the new images
   (migrations first) and waits until every service is healthy. Then
   `scripts/smoke-test.sh` checks the app from outside. It only reads, so it is safe against
   production.
3. Once someone approves the `production` environment, the same images go to **production**
   the same way.

**Off until you turn it on:** publishing and deploying run only while the repository
variable `DEPLOY_ENABLED` is `true` (Settings → Secrets and variables → Actions →
Variables). Without it, a merge to `main` only checks that both images build, so nothing is
published and no deploy fails for lack of a server.

Pull requests into `main` build both images without publishing them. One frontend image
serves every environment: nginx gives the app its environment's settings (the
`SENTRY_*` values) when it starts.

**Rolling back:** Actions → Deploy → Run workflow, pick the environment and enter the full
commit SHA of an earlier release (the Release workflow's runs list them). Migrations are not
reversed. If a later release changed the schema in a way the older code can't use, restore
the backup that deploy took (`make db-backups`, `make db-restore`, run on the server).

`make smoke URL=https://docsphere.example.com` runs the outside checks against any
deployment by hand.

### Setting up a server

Once for each environment (`staging`, `production`):

1. A Linux server with Docker Engine and the compose plugin, behind a TLS-terminating load
   balancer that forwards to `APP_PORT` (see above).
2. A deploy user in the `docker` group. Make a new SSH key pair for it and add the public half
   to its `~/.ssh/authorized_keys`.
3. A directory for the app, e.g. `/srv/docsphere`, holding the `.env` described above, plus
   `BACKEND_IMAGE=ghcr.io/<owner>/docsphere-backend`,
   `FRONTEND_IMAGE=ghcr.io/<owner>/docsphere-frontend` and the environment's
   `SENTRY_ENVIRONMENT`. Each deploy copies in the rest, and records the release in
   `IMAGE_TAG`.
4. In GitHub, under Settings → Environments, create the environment with:
   - variables `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH` (the directory),
     `DEPLOY_KNOWN_HOSTS` (the output of `ssh-keyscan <host>`, so the workflow knows it is
     talking to your server) and `BASE_URL` (the app's URL);
   - secret `DEPLOY_SSH_KEY` (the private half of the key);
   - deployment branches limited to `main`. On `production`, also add **required
     reviewers**: that's the approval step.
5. Set the repository variable `DEPLOY_ENABLED` to `true`, then deploy: re-run the latest
   Release workflow, or run Deploy by hand. The server pulls the
   images with the workflow's own short-lived token, so it needs no registry password of
   its own.

### Dependencies

Dependabot (`.github/dependabot.yml`) opens weekly pull requests into `develop` for Python,
npm, GitHub Actions and the Docker images. CI's `audit` job fails on any known
vulnerability in what production runs (`make audit`: `pip-audit` on
`requirements/base.txt`, `npm audit --omit=dev`) and reports development tooling's as a
warning (`make audit-dev`). In the repository's settings, turn on Dependabot alerts and
security updates, so fixes arrive as soon as an advisory is published.

### Backups

The `backup` service dumps the database (`pg_dump` custom format) and archives the files
attached to documents beside it (`docsphere-<time>.files.tar.gz`, from the `media` volume)
when it starts and then every `BACKUP_INTERVAL_SECONDS` (default daily), and deletes
backups older than `BACKUP_RETENTION_DAYS` (default 14). They live in the `db_backups` volume on the same
server, so also copy them somewhere else (`docker compose cp backup:/backups ./backups`,
then your usual off-site copy).

- `make db-backup` takes one now; `make db-backups` lists them.
- **Restoring:** `make db-restore BACKUP=docsphere-20261008T000000Z.dump` stops the app,
  replaces the database with that dump in one transaction (all or nothing), replaces the
  attached files with those archived beside it, and starts the app again. Everything written after the dump is lost, so take a fresh backup first if you
  may want to go back.

### Checking the stack

`make docker-smoke` builds the stack from `.env` and checks it through nginx: every service
healthy without any manual step, the app's files and routes, Django behind the same origin,
the cookie's production flags, scheduled tasks reaching the worker, the upload size limit
and file storage for attachments, and a backup → change → restore round trip (files
included). It includes the read-only checks every deploy runs
(`scripts/smoke-test.sh`). CI runs it on every pull request, and lints the workflows and
shell scripts (`make lint-scripts`).

For local development, see [CONTRIBUTING.md](CONTRIBUTING.md).
