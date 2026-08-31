.DEFAULT_GOAL := help

.PHONY: help install migrate makemigrations run shell test lint format \
        up down build logs docker-migrate docker-shell clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## Install Python dependencies into the local venv
	pip install -r requirements.txt

migrate: ## Apply database migrations (local)
	python manage.py migrate

makemigrations: ## Generate new migrations (local)
	python manage.py makemigrations

run: ## Run the dev server (local)
	python manage.py runserver 0.0.0.0:8000

shell: ## Open the Django shell (local)
	python manage.py shell

test: ## Run the test suite (local)
	python manage.py test

lint: ## Run ruff
	ruff check .

format: ## Run black + ruff --fix
	black .
	ruff check --fix .

up: ## Start services with docker compose
	docker compose up

build: ## Build docker images
	docker compose build

down: ## Stop and remove docker compose services
	docker compose down

logs: ## Tail docker compose logs
	docker compose logs -f

docker-migrate: ## Apply database migrations (inside the web container)
	docker compose run --rm web python manage.py migrate

docker-shell: ## Open a shell inside the web container
	docker compose run --rm web bash

clean: ## Remove Python cache files
	find . -type d -name __pycache__ -not -path './venv/*' -exec rm -rf {} +
