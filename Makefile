.PHONY: help env up up-lite up-langfuse down logs ps test test-backend test-demo-db test-frontend test-e2e lint format seed migrate index smoke prompts eval-smoke eval eval-data

APP_SERVICES := app-db target-db qdrant backend frontend

help:  ## Список команд
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n", $$1, $$2}'

env:  ## Создать .env со случайными секретами
	@./scripts/init-env.sh

up: env  ## Поднять сервисы приложения
	docker compose up -d --build

up-lite: up  ## То же, что up (оставлено для совместимости)

up-langfuse: env  ## Дополнительно поднять локальный Langfuse (http://localhost:3001)
	docker compose --profile langfuse-local up -d

down:  ## Остановить все сервисы
	docker compose --profile langfuse-local down

ps:  ## Статус сервисов
	docker compose ps

logs:  ## Логи backend
	docker compose logs -f backend

test: test-backend test-demo-db test-frontend  ## Все тесты (нужны запущенные app-db и target-db)

# Отдельная БД app_test: тест миграций откатывает схему до base
test-backend:
	@docker compose exec -T app-db sh -c 'psql -U "$$POSTGRES_USER" -tAc "SELECT 1 FROM pg_database WHERE datname = '"'"'app_test'"'"'" | grep -q 1 || createdb -U "$$POSTGRES_USER" app_test'
	set -a && . ./.env && set +a && cd backend && \
	TEST_DATABASE_URL="postgresql://$$APP_DB_USER:$$APP_DB_PASSWORD@localhost:$$APP_DB_PORT/app_test" \
	TEST_DEMO_DB_URL="postgresql://$$TARGET_DB_READER_USER:$$TARGET_DB_READER_PASSWORD@localhost:$$TARGET_DB_PORT/$$TARGET_DB_NAME" \
	uv run pytest --cov --cov-report=term-missing:skip-covered --cov-fail-under=80

test-demo-db:
	cd demo_db && uv run pytest

test-frontend:
	cd frontend && npm test && npm run build

# E2E против запущенного стека; ответы агента проверяются по заглушке — нужен AGENT_MODE=fake в .env
test-e2e:  ## E2E-тесты Playwright (стек с AGENT_MODE=fake)
	set -a && . ./.env && set +a && cd frontend && \
	E2E_BASE_URL=$${E2E_BASE_URL:-http://localhost:$${FRONTEND_PORT:-3000}} npm run test:e2e

lint:  ## Линтеры и проверка типов
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests evals
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

index:  ## Переиндексировать все источники данных в Qdrant
	docker compose exec backend python -m scripts.reindex_all

smoke:  ## Smoke-тест агента с настоящим LLM на 10 вопросах (нужен OPENAI_API_KEY)
	cd backend && uv run python -m scripts.smoke_agent

prompts:  ## Загрузить промпты в Langfuse (новая версия — только при изменении текста)
	cd backend && uv run python -m scripts.push_prompts "$(MSG)"

eval-smoke:  ## Smoke-eval: 50 вопросов, пороги регрессии (нужен OPENAI_API_KEY, ~$0,4)
	cd backend && uv run python -m evals.smoke

eval:  ## Прогон набора: make eval SUITE=spider_subset CONFIG=agent SEED=1 [LIMIT=20]
	cd backend && uv run python -m evals.run --suite $(SUITE) --config $(CONFIG) --seed $(or $(SEED),1) $(if $(LIMIT),--limit $(LIMIT))

eval-data:  ## Скачать Spider/BIRD, загрузить базы в target-db, собрать наборы
	./scripts/eval-data.sh
