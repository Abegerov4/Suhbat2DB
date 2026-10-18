.PHONY: help env up up-lite down logs ps test test-backend test-demo-db test-frontend lint format seed migrate index eval-smoke

APP_SERVICES := app-db target-db qdrant backend frontend

help:  ## Список команд
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

env:  ## Создать .env со случайными секретами
	@./scripts/init-env.sh

up: env  ## Поднять все сервисы, включая Langfuse
	docker compose up -d --build

up-lite: env  ## Поднять сервисы без Langfuse
	docker compose up -d --build $(APP_SERVICES)

down:  ## Остановить все сервисы
	docker compose down

ps:  ## Статус сервисов
	docker compose ps

logs:  ## Логи backend
	docker compose logs -f backend

test: test-backend test-demo-db test-frontend  ## Все тесты (нужны запущенные app-db и target-db)

# Отдельная БД app_test: тест миграций откатывает схему до base
test-backend:
	@docker compose exec -T app-db sh -c 'psql -U "$$POSTGRES_USER" -tAc "SELECT 1 FROM pg_database WHERE datname = '"'"'app_test'"'"'" | grep -q 1 || createdb -U "$$POSTGRES_USER" app_test'
	set -a && . ./.env && set +a && cd backend && \
	TEST_DATABASE_URL="postgresql://$$APP_DB_USER:$$APP_DB_PASSWORD@localhost:$$APP_DB_PORT/app_test" uv run pytest --cov --cov-report=term-missing:skip-covered --cov-fail-under=80

test-demo-db:
	cd demo_db && uv run pytest

test-frontend:
	cd frontend && npm run build

lint:  ## Линтеры и проверка типов
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
	cd demo_db && uv run ruff check . && uv run ruff format --check . && uv run mypy seed.py tests
	cd frontend && npm run lint && npm run typecheck && npm run format:check

format:  ## Автоформатирование
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd demo_db && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format

SCALE ?= 1.0
seed:  ## Пересоздать и заполнить демо-БД (SCALE=0.1 — уменьшенный объём)
	cd demo_db && uv run python seed.py --scale $(SCALE)

migrate:  ## Применить миграции БД приложения
	docker compose exec backend alembic upgrade head

index:  ## Проиндексировать схему в Qdrant (роль 5)
	@echo "Будет реализовано в роли 5 (docs/roles/05_ai_agent.md)"

eval-smoke:  ## Быстрый прогон evals (роль 7)
	@echo "Будет реализовано в роли 7 (docs/roles/07_evals.md)"
