# DocSphere

DocSphere lets organizations store, manage and share documents among their members, with
access sold as a Stripe subscription. It's a Django REST API with a React app on top.

**What it does**

- **Organizations and people:** sign up an organization, invite people by email (one at a
  time or from a spreadsheet), make them admins, deactivate them.
- **Projects and documents:** private or public within the organization; shared with
  people as Owner, Editor or Viewer; a Viewer can ask for edit access.
- **Working on documents:** search inside their text, version history with restore, file
  attachments, and protection against two people overwriting each other's changes.
- **Accounts:** names, verified email addresses, changing email and password, two-factor
  sign-in with an authenticator app, deleting your account.
- **For admins:** an activity log of who changed access and membership, a data export, and
  deleting the organization (restorable for 30 days).
- **Notifications:** a bell in the app, and emails, when something is shared with you or
  your request is answered.
- **Billing:** plans and payments through Stripe, with a grace period when a payment fails.

**Contents**

1. [Run it on your machine](#run-it-on-your-machine)
2. [Find your way around](#find-your-way-around)
3. [Optional extras](#optional-extras)
4. [Run the tests](#run-the-tests)
5. [Troubleshooting](#troubleshooting)
6. [How the code is organized](#how-the-code-is-organized)
7. [Deploying](#deploying)

To change the code, read [CONTRIBUTING.md](CONTRIBUTING.md) as well. It covers the rules
the code follows, the branch and pull request workflow, and recipes for common changes.

## Run it on your machine

This takes about ten minutes. You'll run two programs side by side: the API (Django, on
port 8000) and the app (React, on port 3000).

### 1. Install the tools

| Tool | Version | Check with |
| --- | --- | --- |
| Git | any | `git --version` |
| Python | 3.12 | `python3.12 --version` |
| Node.js | 22.22 or a later 22.x | `node --version` |
| make | any | `make --version` |

- **macOS:** `brew install python@3.12 node@22`. make comes with the Xcode command-line
  tools (`xcode-select --install`).
- **Linux:** Python 3.12 and make from your package manager. Node from
  [nodejs.org](https://nodejs.org) or [nvm](https://github.com/nvm-sh/nvm): `nvm install 22`.
  The repository's `frontend/.nvmrc` names the version, so `cd frontend && nvm use` picks it.
- **Windows:** use WSL (Ubuntu), then follow the Linux steps. The commands below assume a
  Unix shell.

You don't need a database server, Redis or Docker for this. The API uses a local SQLite
file, and background jobs such as sending email run inside each request.

### 2. Get the code

```sh
git clone git@github.com:abdulwahab015/docsphere.git
cd docsphere
```

All commands below run from this folder unless they say otherwise.

### 3. Set up the API

```sh
python3.12 -m venv venv          # a private Python environment for this project
source venv/bin/activate         # run this again in every new terminal
make install                     # installs the Python packages
cp .env.example .env             # the settings file
```

Open `.env` in an editor and change one line:

```sh
CELERY_TASK_ALWAYS_EAGER=True
```

This sends emails straight away instead of through a separate worker. With `False`, the
default, nothing is sent unless Redis and a Celery worker are running.

The other values are placeholders that work as they are on your machine. Stripe keys only
matter if you want to try payments (see [Optional extras](#optional-extras)).

Then create the database and load the demo data:

```sh
make migrate
python manage.py seed_e2e frontend/e2e/seed.json
```

The second command fills the empty database with demo organizations, people, projects and
documents. It's the same data the end-to-end tests use, and it ends with
"Seeded 22 organizations." It only works on an empty database (see
[Troubleshooting](#troubleshooting)).

Start the API and leave this terminal running:

```sh
make run
```

Check it: <http://localhost:8000/healthz/> should show `{"status": "ok"}`.

### 4. Set up the app

In a **second terminal**, from the same folder:

```sh
cp frontend/.env.example frontend/.env
make fe-install                  # installs the JavaScript packages
make fe-dev                      # starts the app
```

### 5. Log in

Open **<http://localhost:3000>**. Use `localhost`, not `127.0.0.1`: the login cookie only
works when the app and the API are both on `localhost`.

Log in as `admin@acme.e2e.test` with password `E2e-Pass-123!`. Every demo account uses the
same password.

## Find your way around

### Demo accounts

| Account | What you'll see |
| --- | --- |
| `admin@acme.e2e.test` | An organization's admin: People, Activity, Billing and Organization settings (no content yet: create some) |
| `member@acme.e2e.test` | The same organization as an ordinary member |
| `owner@sharing.e2e.test`, `alex@sharing.e2e.test` | Projects and documents shared at different levels |
| `admin@docs.e2e.test` | Documents with sharing and an attached file, and an activity log to read |
| `admin@team.e2e.test` | Invitations, roles and deactivated members |
| `writer@docs.e2e.test` | Documents shared with them, and notifications about it in the bell |
| `admin@lapsed.e2e.test` / `member@lapsed.e2e.test` | An organization whose subscription ended: the subscribe screen / "ask your admin" |
| `admin@overdue.e2e.test` | A failed renewal payment: the warning banner |
| `admin@twofactor.e2e.test` | Two-factor sign-in (see below) |
| `member@held.e2e.test` | An organization that requires two-factor sign-in, before it's set up |
| `admin@deleted.e2e.test` | A deleted organization waiting to be purged, which its admin can restore |

The full list is in `frontend/e2e/seed.json`.

### Emails

Nothing is really emailed on your machine. Each email (invitations, password resets,
verification links, share notices) is printed in the terminal running `make run`. Copy the
link from it into the browser.

### Signing up a new organization

You can create your own organization at <http://localhost:3000/signup>. The new admin first
verifies their email address with the link printed in the `make run` terminal. After that
the app asks them to subscribe. Without Stripe set up, that's as far as a new organization
gets; the demo organizations are already subscribed.

### Two-factor sign-in

Logging in as `admin@twofactor.e2e.test` asks for a code from an authenticator app. To get
codes, add that account's `two_factor_secret` from `frontend/e2e/seed.json` to an app such
as Google Authenticator, 1Password or Authy (choose "enter a setup key"). To try setting it
up from scratch, log in as any other demo account and open Account settings, under the
menu at the bottom of the sidebar.

### The Django admin and the API

- **Django admin:** create an account with `python manage.py createsuperuser`, then go to
  <http://localhost:8000/admin/>. A superuser belongs to no organization, so the app itself
  shows them a "No organization" screen.
- **API documentation:** <http://localhost:8000/api/docs/> lists every endpoint, and you
  can try them from there.
- **Postman:** `postman/` holds a collection of requests that walks through the API.

## Optional extras

### Try real payments (Stripe test mode)

1. Create a free Stripe account and stay in **test mode**. Create a product with one or more
   recurring prices.
2. In `.env`, set `STRIPE_TEST_SECRET_KEY`, `STRIPE_TEST_PUBLIC_KEY` and
   `STRIPE_PRODUCT_ID` (the product's id, `prod_…`).
3. Copy the product and prices into the local database:
   `python manage.py djstripe_sync_models Product Price`
4. Install the [Stripe CLI](https://docs.stripe.com/stripe-cli), run `stripe login` once,
   then keep `make stripe-listen` running in a third terminal. It forwards Stripe's
   webhooks, which is how a payment switches the subscription on.
5. Subscribe from the app with card number `4242 4242 4242 4242`, any future expiry date and
   any CVC.

### Run background jobs the way production does

Start Redis (for example `docker run --rm -p 6379:6379 redis:7-alpine`), set
`CELERY_TASK_ALWAYS_EAGER=False` in `.env`, and run `make worker` in another terminal. Emails
are then sent by the worker and printed in its terminal. `make beat` also runs the daily
jobs: renewal reminders and clean-ups.

### Run everything in Docker

With Docker installed, `make up` starts the whole stack with development settings and your
code mounted: Postgres, Redis, the API on port 8000, a worker, the scheduler, Flower (the
worker dashboard) on port 5555, and the built app on port 8080. The first start downloads
and builds images, so it takes a few minutes. Stop it with `make down`.

## Run the tests

| Command | What it checks |
| --- | --- |
| `make check` | The backend, as CI does: settings, migrations, formatting, lint, and every test, with coverage |
| `make fe-check` | The frontend, as CI does: formatting, lint, types, every test, with coverage, and the production build |
| `make fe-e2e` | End to end in a real browser, against a real API on a fresh database (ports 8001 and 3100, so your running servers aren't touched). Before the first run: `cd frontend && npx playwright install chromium` |
| `make test-pg` | The backend tests on Postgres, the production database (needs Docker) |
| `make docker-smoke` | Builds the production stack and checks it from outside (needs Docker) |

`make help` lists every command.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| The app loads, but logging in fails or loops back to the login page | Open the app at `http://localhost:3000`, not `127.0.0.1`. `frontend/.env` must say `VITE_API_BASE_URL=http://localhost:8000`. |
| `UndefinedValueError: … not found` when starting the API | `.env` is missing a setting. Compare it with `.env.example`; every value there is required. |
| No emails appear in the `make run` terminal | Set `CELERY_TASK_ALWAYS_EAGER=True` in `.env` and restart `make run`. |
| `seed_e2e` fails | It needs an empty database. Delete `db.sqlite3`, run `make migrate`, then seed again. |
| `npm warn EBADENGINE … node >=22.22.0` | Your Node is older than the project wants. Install a newer 22.x (`nvm install 22`). |
| "That port is already in use" | Something else is on 8000 or 3000. Stop it; the app's port is fixed at 3000 because the API's settings expect it. |
| A new organization only shows "Subscribe to continue" | Expected without Stripe. Use a demo account, or set up Stripe test mode. |
| `command not found: make` | Install make (macOS: `xcode-select --install`). On Windows, use WSL. |

## How the code is organized

```text
core/            Settings (core/settings/), URLs, Celery, and shared plumbing
users/           People, invitations, logging in, two-factor sign-in
organizations/   Organizations: signup, profile, deletion, data export
projects/        Projects, documents, sharing, access requests, versions, attachments
audit/           The activity log admins read
notifications/   The notifications behind the bell
subscriptions/   Plans, checkout, billing portal, renewal reminders
clients/         Calls to Stripe
frontend/        The React app (see frontend/README.md)
postman/         API requests to try by hand
scripts/         Smoke tests, backups, deploy scripts
```

Each part of the API lives in `<app>/api/v1/` and is served under `/api/v1/<app>/`.
[CONTRIBUTING.md](CONTRIBUTING.md) explains the rules behind it: tenant isolation, how
document access is decided, and the API and test conventions.

## Deploying

DocSphere hasn't been deployed anywhere yet. Everything below is ready, but the release
pipeline is switched off (see [Releases](#releases)). Before a first real deployment:

- **Fill in the production `.env`:** a long random `SECRET_KEY`; `ALLOWED_HOSTS`,
  `FRONTEND_URL` and `CORS_ALLOWED_ORIGINS` for your domain; SMTP settings so email really
  goes out; Stripe live keys and `STRIPE_PRODUCT_ID`; `SENTRY_DSN` and
  `SENTRY_FRONTEND_DSN` for error reports (optional); a hard-to-guess
  `DJANGO_ADMIN_PATH`; and `SECURE_HSTS_SECONDS`, raised over time once HTTPS is proven.
- **Rehearse on staging first.** The deploy scripts were only rehearsed against a local
  test server, never a real host. Deploy to staging, then run `make smoke URL=…` against it.
- **Decide on what isn't there yet:** backups and attached files stay on the server's own
  volumes (copy them off-site); uploaded files aren't virus-scanned; the two-factor keys
  are stored unencrypted in the database.

`docker-compose.yml` is the production stack:

| Service | What it is |
| --- | --- |
| `frontend` | nginx: serves the built app and forwards Django's paths to `web`. The only published port (`APP_PORT`, default 8080). |
| `web` | Django on gunicorn (`core.settings.production`), reachable only inside the stack. Files attached to documents, and organizations' data exports, are stored on its `media` volume. |
| `worker`, `flower` | Celery worker, and its dashboard |
| `beat` | Sends scheduled tasks (the daily renewal reminders and clean-ups) to the worker. Run exactly one. |
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
