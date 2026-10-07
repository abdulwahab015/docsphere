# DocSphere

## Deploying

`docker-compose.yml` is the production stack:

| Service | What it is |
| --- | --- |
| `frontend` | nginx: serves the built app and forwards Django's paths to `web`. The only published port (`APP_PORT`, default 8080). |
| `web` | Django on gunicorn (`core.settings.production`), reachable only inside the stack |
| `worker`, `flower` | Celery worker, and its dashboard |
| `beat` | Sends scheduled tasks (the daily renewal reminders) to the worker. Run exactly one. |
| `db`, `redis` | Postgres, and the Celery broker |
| `migrate` | Applies the database migrations at every start, then exits; the Django services wait for it |
| `backup` | Dumps the database daily into the `db_backups` volume and keeps 14 days of dumps |

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
2. `docker compose up -d --build` (migrations run on their own, before Django starts)
3. In the Django admin, add a dj-stripe **Webhook endpoint** for `https://<your host>`.
   dj-stripe registers it with Stripe, which then calls `/stripe/webhook/<uuid>/`.

To release a new version, pull it and run `docker compose up -d --build` again.

### Backups

The `backup` service dumps the database (`pg_dump` custom format) when it starts and then
every `BACKUP_INTERVAL_SECONDS` (default daily), and deletes dumps older than
`BACKUP_RETENTION_DAYS` (default 14). They live in the `db_backups` volume on the same
server, so also copy them somewhere else (`docker compose cp backup:/backups ./backups`,
then your usual off-site copy).

- `make db-backup` takes one now; `make db-backups` lists them.
- **Restoring:** `make db-restore BACKUP=docsphere-20261008T000000Z.dump` stops the app,
  replaces the database with that dump in one transaction (all or nothing), and starts the
  app again. Everything written after the dump is lost, so take a fresh backup first if you
  may want to go back.

### Checking the stack

`make docker-smoke` builds the stack from `.env` and checks it through nginx: every service
healthy without any manual step, the app's files and routes, Django behind the same origin,
the cookie's production flags, scheduled tasks reaching the worker, and a backup → change →
restore round trip. CI runs it on every pull request.

For local development, see `frontend/README.md` and `make help`.
