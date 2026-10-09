# Working on DocSphere

DocSphere lets organizations store, manage and share documents among their members, with
access sold as a Stripe subscription. This guide covers running it on your machine, testing
it, and the rules the code follows.

- **Backend:** Django + Django REST Framework (`/api/v1/`), Celery for background work,
  dj-stripe for subscriptions. SQLite on your machine, Postgres in production and CI.
- **Frontend:** a React single-page app in `frontend/` that talks to the API over HTTP only
  (`frontend/README.md` covers its tooling).
- **Production stack:** `docker-compose.yml` (see `README.md`).

## Contents

1. [Prerequisites](#prerequisites)
2. [Quick start](#quick-start)
3. [Settings (`.env`)](#settings-env)
4. [Make targets](#make-targets)
5. [Tests](#tests)
6. [Trying things by hand](#trying-things-by-hand)
7. [Branches, commits and pull requests](#branches-commits-and-pull-requests)
8. [How the code is organized](#how-the-code-is-organized)
9. [Rules the code follows](#rules-the-code-follows)
10. [Recipes](#recipes)

## Prerequisites

| Tool | Version | Needed for |
| --- | --- | --- |
| Python | 3.12 | the backend |
| Node | 22.22 or later 22.x (`frontend/.nvmrc`) | the frontend |
| Docker | any recent | optional: `make test-pg`, `make docker-smoke`, `make lint-scripts`, `make up` |
| Stripe CLI | any recent | optional: trying real Stripe test-mode payments |

Redis is only needed to run Celery for real. By default tasks (emails) run inside the request.

## Quick start

From the repository root:

```sh
# Backend
python3.12 -m venv venv
source venv/bin/activate
make install                    # Python dependencies, incl. dev tooling
cp .env.example .env            # then see "Settings" below
make migrate
make run                        # API on http://localhost:8000

# Frontend, in a second terminal
cp frontend/.env.example frontend/.env
make fe-install
make fe-dev                     # app on http://localhost:3000
```

Open **http://localhost:3000**, not `127.0.0.1`. The refresh-token cookie is only shared
between the app and the API when both are on the same site.

To get accounts and data to sign in with, seed the database (see
[Seeded accounts](#seeded-accounts)), or sign up a new organization from the app. A new
signup must verify its email first: the link is printed in the `runserver` terminal.

Install the pre-commit hooks once, so black, ruff, Prettier and oxlint run on every commit:

```sh
pre-commit install
```

## Settings (`.env`)

`.env.example` lists every setting the backend reads. For local development, a copy works
with two changes:

```sh
CELERY_TASK_ALWAYS_EAGER=True   # run tasks (emails) inside the request: no Redis or worker
```

and, only if you'll try payments, your Stripe **test-mode** keys plus the product whose
prices are your plans (`STRIPE_TEST_SECRET_KEY`, `STRIPE_TEST_PUBLIC_KEY`,
`STRIPE_PRODUCT_ID`). The placeholder values are fine otherwise.

Good to know:

- **Emails are printed** in the `make run` terminal, as written, so their links can be
  copied (`core/email.py::ConsoleEmailBackend`). The `EMAIL_*` SMTP values are only used in
  production, or if you set `EMAIL_BACKEND` yourself.
- **Settings modules:** `core.settings.local` is the default (`DEBUG` on). Tests use
  `core.settings.test` (the Make targets set it), and the Docker stack uses
  `core.settings.production`.
- **Numbers without defaults** (token lifetimes, throttle rates) must be in `.env`, or the
  app refuses to start. That's deliberate.
- `frontend/.env` holds one value: `VITE_API_BASE_URL=http://localhost:8000`.

## Make targets

`make help` lists them all. The ones you'll use:

| Target | What it does |
| --- | --- |
| `make run` | API dev server on :8000 |
| `make fe-dev` | App dev server on :3000, hot reload |
| `make migrate` / `make makemigrations` | Apply / create migrations |
| `make shell` | Django shell |
| `make check` | **Backend CI, locally:** system check, missing migrations, API types up to date, black, ruff, tests with coverage |
| `make fe-check` | **Frontend CI, locally:** Prettier, oxlint, types, tests with coverage, build |
| `make fe-e2e` | End-to-end tests in a real browser |
| `make test` / `make test-cov` | Backend tests only (SQLite) |
| `make test-pg` | Backend tests on a throwaway Postgres 16 (Docker), like CI |
| `make fe-test` / `make fe-test-cov` | Frontend tests only |
| `make format` / `make fe-format` | Format the backend (black + ruff fixes) / the frontend (Prettier) |
| `make lint` / `make fe-lint` | ruff / oxlint |
| `make fe-api-types` | Regenerate `frontend/src/api/schema.d.ts` from the API's schema |
| `make compile` | Recompile `requirements/*.txt` after editing a `.in` file |
| `make audit` / `make audit-dev` | Known vulnerabilities in runtime / all dependencies |
| `make lint-scripts` | actionlint + shellcheck on the workflows and scripts (Docker) |
| `make docker-smoke` | Build the production stack and check it through nginx (Docker, needs `.env`) |
| `make worker` / `make beat` | Celery worker / scheduler (needs Redis and `CELERY_TASK_ALWAYS_EAGER=False`) |
| `make stripe-listen` | Forward Stripe test-mode webhooks to `make run` |
| `make up` / `make down` | The whole stack in Docker with development settings and your code mounted (Postgres, Redis, worker, beat, Flower) |

## Tests

| Suite | Run | What it covers |
| --- | --- | --- |
| Backend | `make check` (or `make test`) | Every endpoint, permission rule, task and command. Each request is wrapped in `assertNumQueries`, so an N+1 query fails the test. Coverage must stay at 95% or more. |
| Backend on Postgres | `make test-pg` | The same suite on production's database. Row-lock (concurrency) tests run only here; SQLite skips them. |
| Frontend | `make fe-check` (or `make fe-test`) | Components and pages through the real route table, with the API mocked at the network level (MSW). Coverage at 95% or more. |
| End-to-end | `make fe-e2e` | A real browser against the real API on a fresh seeded database (API on :8001, app on :3100; your dev servers are untouched). The first run needs `cd frontend && npx playwright install chromium`. It also checks every page for accessibility and phone layout. |
| Production stack | `make docker-smoke` | Builds the images, starts the whole stack and checks it from outside (health, headers, cookies, background tasks, backup and restore). |

**Before a pull request**, run `make check`, `make fe-check` and `make fe-e2e`, plus
`make docker-smoke` if you touched a Dockerfile, compose, nginx or settings. CI runs all of
them (backend on Postgres, shuffled; see `.github/workflows/ci.yml`), plus the dependency
audit and the workflow/script linters.

When a test fails only in CI's shuffled run, its log prints the seed:
`python manage.py test --shuffle <seed>` repeats that order locally.

## Trying things by hand

### Seeded accounts

The end-to-end tests' data (`frontend/e2e/seed.json`) works as demo data too. On an
**empty** database (a fresh `db.sqlite3`, or delete it and `make migrate` again):

```sh
python manage.py seed_e2e frontend/e2e/seed.json
```

Every account's password is `E2e-Pass-123!`. Some useful ones:

| Account | What you'll see |
| --- | --- |
| `admin@acme.e2e.test` / `member@acme.e2e.test` | A subscribed organization, as its admin / a member |
| `owner@sharing.e2e.test`, `alex@sharing.e2e.test` | Projects and documents shared at different levels |
| `admin@team.e2e.test` | People management: invitations, roles, deactivated members |
| `admin@lapsed.e2e.test` / `member@lapsed.e2e.test` | An organization without a subscription (the subscribe screen / "ask your admin") |
| `admin@overdue.e2e.test` | A failed renewal payment (the payment warning banner) |

The command refuses to run outside local and test settings, so it can never seed production.
For the Django admin, `python manage.py createsuperuser` (a superuser belongs to no
organization, so the app itself shows them a "No organization" screen).

`postman/` has a collection for exploring the API by hand. The API's own docs are at
http://localhost:8000/api/docs/.

### Emails

Emails (invitations, password resets, share notices) appear in the `make run` terminal.
Copy the link out of them; it points at `http://localhost:3000`. With Celery running for
real, they appear in the `make worker` terminal instead.

### Stripe test mode

1. In the Stripe dashboard (test mode), create a product with recurring prices. Put its id
   in `STRIPE_PRODUCT_ID` and the test keys in `.env`.
2. Copy the product and prices into the local database:
   `python manage.py djstripe_sync_models Product Price`
3. `stripe login` once, then keep `make stripe-listen` running next to `make run`. It
   forwards Stripe's webhooks, which is how a payment activates the subscription.
4. Subscribe from the app with card `4242 4242 4242 4242`, any future date and any CVC.

### Celery for real

Tasks normally run inside the request (`CELERY_TASK_ALWAYS_EAGER=True`). To run them the way
production does, start Redis (`docker run --rm -p 6379:6379 redis:7-alpine`), set
`CELERY_TASK_ALWAYS_EAGER=False`, and run `make worker` (and `make beat` for the daily
renewal reminders).

## Branches, commits and pull requests

- **Branch from `develop`**, one branch per change, named for what it is: `feat/…`, `fix/…`,
  `chore/…`, `docs/…`, `test/…`, `ci/…`. Don't start a branch from another unmerged branch:
  pull requests are squash-merged, so the second one would need rebasing afterwards.
- **Commit messages** are one line, `type: summary`, like the existing history
  (`feat: add project restore endpoint`). A pull request becomes one commit on `develop`,
  titled the same way.
- **Pull requests** go into `develop`. Say what changed and why, how it was tested (the
  suites' results), and anything a reviewer should look at closely. A bug fix comes with a
  test that fails without the fix.
- **A backend change that alters the API** ships with the regenerated
  `frontend/src/api/schema.d.ts` (`make fe-api-types`). CI fails if it's out of date.
- **Dependabot** opens weekly update pull requests. Review majors like any other change.
  Postgres, Redis, Node and Python releases are left out on purpose: each is a planned
  upgrade (see the comments in `.github/dependabot.yml`).
- **Releases:** `main` gets `develop` when a version is ready. The release and deploy
  workflows exist but stay **off** unless the repository variable `DEPLOY_ENABLED` is `true`
  (README "Releases"); without it, a merge to `main` only checks that the images build.

## How the code is organized

```text
core/            settings/ (base, local, test, production), URLs, Celery, and shared plumbing:
                 the base model, pagination, request logging, email, health check,
                 subscription gate, error reporting. No business models.
users/           User (email login, no username), Invitation, authentication endpoints
organizations/   Organization, its signup and profile, its subscription properties
projects/        Project, Document, their permissions, sharing and access requests
subscriptions/   Plans, checkout, billing portal, renewal reminders
clients/         Code that calls Stripe over the network (not a Django app)
frontend/        The React app (frontend/README.md)
scripts/         Smoke tests, backups, Postgres test runner, deploy scripts
requirements/    base.in / dev.in (edit these) compiled to base.txt / dev.txt
```

Each app's API lives in `<app>/api/v1/{serializers,urls,views}.py`, mounted under
`/api/v1/<app>/`.

## Rules the code follows

These are the decisions everything else rests on. Breaking one is a bug even if the tests
still pass, so a change that touches them needs a test that pins them down.

### Tenants and access

- **Every query is scoped to the caller's organization.** Use the managers
  (`Project.objects.for_organization(org)`, `.visible_to(user)`), never a bare
  `.objects.all()`. One organization must never see another's data.
- **Private means private.** A `PRIVATE` project or document is invisible to anyone
  without an explicit permission, organization admins included. To someone who can't see
  it, it doesn't exist: the API answers **404**, never 403, and the app says "Not found".
- **Access levels:** Owner > Editor > Viewer. Owner can edit, delete and share; Editor can
  edit; Viewer can read.
- **How a document's access is decided:** the user's own permission on the document, at
  whatever level; otherwise a `PUBLIC` document gives every member of its organization
  Viewer; otherwise nothing. **A project's permissions never apply to its documents.**
  They only decide who may create documents inside the project.
- **There is always an Owner.** The last active Owner of something can't lower or remove
  themselves, and an organization always keeps an admin. These checks run under a row lock,
  so two people changing each other at once can't both pass.
- **Deactivating a user** (`is_active=False`) is how people are removed. Deactivated users
  can't sign in, be shared with, or receive emails. Nothing is hard-deleted, and every
  project and document keeps its creator.
- **A new signup verifies its email before anything else.** Until they open the emailed
  link, the API refuses them everywhere with **403** `email_unverified` (checked before the
  subscription), except to verify, ask for a new link, read `/users/me/` and log out.
  Invited members start verified: their invitation link proves the address. A signup that
  hasn't verified within `EMAIL_LINK_EXPIRY_SECONDS` loses its address, so whoever owns it
  can sign up or be invited with it, which removes the old account and its empty
  organization; a daily task removes the rest. Changing an email works the same way: a
  link to the new address, which signs the account out everywhere when opened.

### Subscriptions

- An organization without an active subscription gets **402** from every endpoint except
  the ones needed to sign in and pay. Read the status through
  `Organization.active_subscription`, never by querying dj-stripe directly. `past_due`
  (Stripe is retrying a failed payment) still counts as active.
- Code that calls Stripe over the network lives in `clients/stripe.py`. Reading
  dj-stripe's already-synced tables is an ordinary query and stays where it's needed.

### The API

- Raise DRF's exceptions (`NotFound`, `PermissionDenied`, `ValidationError`) and use
  `rest_framework.generics.get_object_or_404`, never Django's `Http404`.
- Password-policy errors are reported under the password field
  (`users/validators.py::validate_password_for_field`).
- Sensitive endpoints (login, signup, password reset, checkout, …) have their own throttle
  scope, with the rate in `.env`.
- Emails are sent from Celery tasks declared with `core/email.py::email_task` (it retries
  failed sends), with the wording in template files, never inline. Tasks take ids, not model
  instances.
- Every list endpoint is paginated and ordered.

### Code style

- **Backend:** black formats, ruff lints (a broad rule set). Fix what ruff flags rather than
  silencing it. Choices go in `choices.py`, managers in `managers.py`, lookup tables in
  `mappings.py`. Use `get_user_model()` in code and `settings.AUTH_USER_MODEL` in model
  fields.
- **Frontend:** Prettier formats, oxlint lints. Named exports only, imports through `@/`,
  no `any`.
- **Both:** one job per function or component; repeated logic gets extracted once it
  appears twice; descriptive names (no single-letter callback parameters); comments say
  *why*, not what.

### The frontend

- **Server data lives only in TanStack Query.** Each feature has `api.ts` (typed request
  functions), `query-keys.ts` and `hooks.ts`. Components call the hooks, and never copy
  query data into state.
- **API types are generated** (`src/api/schema.d.ts`), never written by hand.
- **The session:** the access token is kept in memory only, and the refresh token is an
  HttpOnly cookie the app never reads. A 401 refreshes once and retries; 401 and 402 are
  handled in one place (`src/app/query-client.ts`), not per screen.
- **Hiding a button is a convenience.** The API enforces every rule, and the UI decides
  what to show from the API's `access_level` / `org_role` (`lib/access.ts::can`).
- **Routes** come from `PATHS` (`src/app/paths.ts`). Forms use React Hook Form + Zod, with
  the server's field errors mapped onto the inputs (`lib/form-errors.ts::applyApiErrors`).

### Tests

- **Backend:** build data with the factories (`<app>/factories.py`), wrap each request in
  `assertNumQueries`, and order tests happy path first, then the refusals.
- **Frontend:** query the page the way a person would (`getByRole`, `getByLabelText`) and
  mock the network with MSW, never the API modules. Render pages through `renderRoute`, so
  guards and redirects are exercised too.

## Recipes

### Add an API endpoint

1. Serializer and view in `<app>/api/v1/`, route in its `urls.py` (`name=` with
   underscores). Scope the queryset to the organization, and check access with the existing
   helpers (`projects/permissions.py`).
2. Leave the default permissions where you can. A view that sets its own
   `permission_classes` lists `HasVerifiedEmail` after the authentication check, and
   `HasActiveSubscription` unless it must work without a subscription.
   `users.tests.EmailVerificationGateTests` checks every endpoint, and fails for one that
   lets an unverified signup through.
3. A bare `APIView` needs `@extend_schema(...)`, or the schema can't describe it.
4. Tests: the happy path, each refusal (404 for things the caller can't see), another
   organization's data, all with `assertNumQueries`.
5. `make fe-api-types`, and commit `schema.d.ts` with the change.

### Add a page to the app

1. Add its path to `PATHS`, and its route to `src/app/routes.tsx` with
   `lazy: lazyPage(...)` (every page is loaded on demand).
2. Start the page with `<PageHeader title=…>`. For a sidebar entry, add it to
   `src/app/navigation.ts::NAV_ITEMS`.
3. Tests through `renderRoute`. Add an end-to-end spec in `frontend/e2e/`, and a line for
   the page in `e2e/accessibility.spec.ts`.

### Add an end-to-end account or data

Add it to `frontend/e2e/seed.json` (organizations, users, projects, documents, sharing).
Both `seed_e2e` and the tests read that file. A test that changes shared data gets its own
organization, so tests can't disturb each other.

### Add a setting

Read it in `core/settings/base.py` with `config(...)`, and add it to `.env.example`. A
setting with no default must also be added to:

- the `env:` block in `.github/workflows/ci.yml`;
- the placeholder list in `Dockerfile`, because `collectstatic` loads the production
  settings while the image builds.

Then run `make docker-smoke`.

### Add a dependency

Python: add it to `requirements/base.in` (runtime) or `dev.in` (tools and tests), then
`make compile` and commit the `.txt` files. npm: a package that ends up in the app goes in
`dependencies`; build and test tools go in `devDependencies`, which keeps the runtime audit
meaningful.

### Add a background job or email

Write a task in the app's `tasks.py`: `email_task` for emails, with the wording in
`<app>/templates/<app>/email/*.subject.txt` and `*.body.txt`, and `@shared_task` otherwise.
Call it with `.delay(id)`. A periodic job also goes in `CELERY_BEAT_SCHEDULE`; a test fails
if the scheduled name isn't a registered task.
