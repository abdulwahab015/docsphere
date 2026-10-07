.DEFAULT_GOAL := help

DC_DEV := docker compose -f docker-compose.yml -f docker-compose.dev.yml
FE_NPM := npm --prefix frontend
# Relative to frontend/, where npm runs the script.
FE_SCHEMA := node_modules/.tmp/openapi.yaml
FE_TYPES := src/api/schema.d.ts
FE_TYPES_CHECK := node_modules/.tmp/schema.d.ts
# The end-to-end API's throwaway database (repo-relative: no spaces in the URL).
E2E_DATABASE := frontend/node_modules/.tmp/e2e.sqlite3
# Where the end-to-end API writes the emails it sends; e2e/fixtures.ts reads them.
E2E_MAILBOX := frontend/node_modules/.tmp/e2e-mail

.PHONY: help install compile migrate makemigrations run shell worker beat flower stripe-listen test test-cov test-pg lint format check \
        up down build logs docker-migrate docker-shell docker-smoke clean \
        fe-install fe-dev fe-build fe-test fe-test-cov fe-lint fe-format fe-check fe-api-types \
        fe-api-types-check fe-e2e e2e-api

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies (incl. dev tooling) into the local venv
	pip install -r requirements/dev.txt

compile: ## Recompile requirements/*.txt from *.in (run after editing an .in file)
	pip-compile --strip-extras -o requirements/base.txt requirements/base.in
	pip-compile --strip-extras -o requirements/dev.txt requirements/dev.in

migrate: ## Apply database migrations (local)
	python manage.py migrate

makemigrations: ## Generate new migrations (local)
	python manage.py makemigrations

run: ## Run the dev server (local)
	python manage.py runserver 0.0.0.0:8000

shell: ## Open the Django shell (local)
	python manage.py shell

worker: ## Run a Celery worker (local; needs Redis and CELERY_TASK_ALWAYS_EAGER=False)
	celery -A core worker -l info

beat: ## Run Celery beat, which sends scheduled tasks (renewal reminders) to the worker (local)
	celery -A core beat -l info

flower: ## Run the Flower dashboard (local; needs FLOWER_BASIC_AUTH + a broker)
	celery -A core flower --conf=core/settings/flowerconfig.py

stripe-listen: ## Forward real Stripe test-mode webhooks to the local server (needs the Stripe CLI, `stripe login`)
	python manage.py stripe_listen

test: ## Run the test suite (local)
	DJANGO_SETTINGS_MODULE=core.settings.test python manage.py test

test-cov: ## Run the test suite under coverage and print a report
	DJANGO_SETTINGS_MODULE=core.settings.test coverage run manage.py test
	coverage report

test-pg: ## Run the test suite on a throwaway Postgres 16, like CI (needs Docker)
	./scripts/test-postgres.sh

lint: ## Run ruff
	ruff check .

format: ## Run black + ruff --fix
	black .
	ruff check --fix .

check: ## Run the full CI check sequence locally (system check, migrations, format, lint, coverage)
	python manage.py check
	python manage.py makemigrations --check --dry-run
	$(MAKE) fe-api-types-check
	black --check .
	ruff check .
	DJANGO_SETTINGS_MODULE=core.settings.test coverage run manage.py test
	coverage report

fe-install: ## Install frontend dependencies from the lockfile
	$(FE_NPM) ci

fe-dev: ## Run the frontend dev server on http://localhost:3000
	$(FE_NPM) run dev

fe-build: ## Type-check and build the frontend for production
	$(FE_NPM) run build

fe-test: ## Run the frontend test suite
	$(FE_NPM) run test

fe-test-cov: ## Run the frontend test suite under coverage (fails under threshold)
	$(FE_NPM) run test:cov

fe-lint: ## Run oxlint on the frontend
	$(FE_NPM) run lint

fe-format: ## Run prettier --write on the frontend
	$(FE_NPM) run format

fe-check: ## Run the full frontend CI sequence locally (format, lint, types, coverage, build)
	$(FE_NPM) run format:check
	$(FE_NPM) run lint
	$(FE_NPM) run typecheck
	$(FE_NPM) run test:cov
	$(FE_NPM) run build

fe-api-types: ## Regenerate frontend/src/api/schema.d.ts from the backend's OpenAPI schema
	mkdir -p frontend/$(dir $(FE_SCHEMA))
	python manage.py spectacular --file frontend/$(FE_SCHEMA)
	$(FE_NPM) run api:types -- $(FE_SCHEMA) -o $(FE_TYPES)

fe-api-types-check: ## Fail if frontend/src/api/schema.d.ts is out of date with the backend
	$(MAKE) fe-api-types FE_TYPES=$(FE_TYPES_CHECK)
	@cmp -s frontend/$(FE_TYPES_CHECK) frontend/$(FE_TYPES) || \
		(echo "frontend/$(FE_TYPES) is out of date: run 'make fe-api-types' and commit the result."; exit 1)

fe-e2e: ## Run the Playwright end-to-end tests (starts its own API on :8001 and app on :3100)
	$(FE_NPM) run e2e

e2e-api: export DJANGO_SETTINGS_MODULE := core.settings.test
e2e-api: export DATABASE_URL := sqlite:///$(E2E_DATABASE)
e2e-api: export FRONTEND_URL := $(E2E_APP_ORIGIN)
e2e-api: export CORS_ALLOWED_ORIGINS := $(E2E_APP_ORIGIN)
e2e-api: export EMAIL_BACKEND := django.core.mail.backends.filebased.EmailBackend
e2e-api: export EMAIL_FILE_PATH := $(E2E_MAILBOX)
e2e-api: ## (Started by Playwright) Fresh seeded database, then the API on $$E2E_API_PORT
	@test -n "$(E2E_API_PORT)" -a -n "$(E2E_APP_ORIGIN)" || (echo "Run via 'make fe-e2e'."; exit 1)
	mkdir -p $(dir $(E2E_DATABASE))
	rm -f $(E2E_DATABASE)
	rm -rf $(E2E_MAILBOX)
	python manage.py migrate --noinput --verbosity 0
	python manage.py seed_e2e frontend/e2e/seed.json
	python manage.py runserver $(E2E_API_PORT) --noreload

up: ## Start the dev stack (base + dev overlay)
	$(DC_DEV) up

build: ## Build docker images (dev stack)
	$(DC_DEV) build

down: ## Stop and remove dev-stack services
	$(DC_DEV) down

logs: ## Tail dev-stack logs
	$(DC_DEV) logs -f

docker-migrate: ## Apply database migrations (inside the web container)
	$(DC_DEV) run --rm web python manage.py migrate

docker-shell: ## Open a shell inside the web container
	$(DC_DEV) run --rm web bash

docker-smoke: ## Build the production stack and check it through nginx on :8080 (needs .env)
	./scripts/docker-smoke-test.sh

clean: ## Remove Python cache files
	find . -type d -name __pycache__ -not -path './venv/*' -exec rm -rf {} +
