.DEFAULT_GOAL := help

DC_DEV := docker compose -f docker-compose.yml -f docker-compose.dev.yml
FE_NPM := npm --prefix frontend
# Relative to frontend/, where npm runs the script.
FE_SCHEMA := node_modules/.tmp/openapi.yaml

.PHONY: help install compile migrate makemigrations run shell flower stripe-listen test test-cov lint format check \
        up down build logs docker-migrate docker-shell clean \
        fe-install fe-dev fe-build fe-test fe-test-cov fe-lint fe-format fe-check fe-api-types

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

flower: ## Run the Flower dashboard (local; needs FLOWER_BASIC_AUTH + a broker)
	celery -A core flower --conf=core/settings/flowerconfig.py

stripe-listen: ## Forward real Stripe test-mode webhooks to the local server (needs the Stripe CLI, `stripe login`)
	python manage.py stripe_listen

test: ## Run the test suite (local)
	DJANGO_SETTINGS_MODULE=core.settings.test python manage.py test

test-cov: ## Run the test suite under coverage and print a report
	DJANGO_SETTINGS_MODULE=core.settings.test coverage run manage.py test
	coverage report

lint: ## Run ruff
	ruff check .

format: ## Run black + ruff --fix
	black .
	ruff check --fix .

check: ## Run the full CI check sequence locally (system check, migrations, format, lint, coverage)
	python manage.py check
	python manage.py makemigrations --check --dry-run
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
	$(FE_NPM) run api:types -- $(FE_SCHEMA) -o src/api/schema.d.ts

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

clean: ## Remove Python cache files
	find . -type d -name __pycache__ -not -path './venv/*' -exec rm -rf {} +
