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
2. `docker compose up -d --build`
3. `docker compose run --rm web python manage.py migrate`
4. In the Django admin, add a dj-stripe **Webhook endpoint** for `https://<your host>`.
   dj-stripe registers it with Stripe, which then calls `/stripe/webhook/<uuid>/`.

`make docker-smoke` builds the stack from `.env` and checks it through nginx: the app's
files and routes, Django behind the same origin, and the cookie's production flags. CI runs
it on every pull request.

For local development, see `frontend/README.md` and `make help`.
