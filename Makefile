.DEFAULT_GOAL := help

# Dev stack = prod-safe base + the dev overlay (never auto-loaded).
DC_DEV := docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: help install compile migrate makemigrations run shell flower test test-cov lint format \
        up down build logs docker-migrate docker-shell clean

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

test: ## Run the test suite (local)
	python manage.py test

test-cov: ## Run the test suite under coverage and print a report
	coverage run manage.py test
	coverage report

lint: ## Run ruff
	ruff check .

format: ## Run black + ruff --fix
	black .
	ruff check --fix .

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
