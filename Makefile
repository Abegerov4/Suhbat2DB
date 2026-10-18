.PHONY: help env up up-lite down logs ps test test-backend test-frontend lint format seed index eval-smoke

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

test: test-backend test-frontend  ## Все тесты

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm run build

lint:  ## Линтеры и проверка типов
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app tests
	cd frontend && npm run lint && npm run typecheck && npm run format:check

format:  ## Автоформатирование
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && npm run format

seed:  ## Заполнить демо-БД (роль 2)
	@echo "Будет реализовано в роли 2 (docs/roles/02_database.md)"

index:  ## Проиндексировать схему в Qdrant (роль 5)
	@echo "Будет реализовано в роли 5 (docs/roles/05_ai_agent.md)"

eval-smoke:  ## Быстрый прогон evals (роль 7)
	@echo "Будет реализовано в роли 7 (docs/roles/07_evals.md)"
