# Роль 1. DevOps

**Статус: ✅ выполнена** (октябрь 2026)

**Цель:** окружение, в котором весь проект поднимается одной командой, а качество кода проверяется автоматически.
**Зависит от:** ничего.
**Нужно для:** всех остальных ролей.

## Задачи

### 1.1 Репозиторий
- [x] Ветка `main`, приватный репозиторий https://github.com/Abegerov4/Suhbat2DB
- [x] Структура монорепозитория: `backend/`, `frontend/`, `infra/`, `scripts/`, `docs/` (`evals/` и `demo_db/` появятся в ролях 2 и 7)
- [x] `.gitignore`: личные материалы, `.env`, артефакты Python и Node. Проверено, что обоснование, PDF и `база знаний/` не попадают в индекс
- [ ] GitHub Projects: доска `Backlog / In progress / Review / Done` с задачами из файлов ролей (делается вручную в веб-интерфейсе GitHub)
- [ ] Доступ руководителя к репозиторию (Settings → Collaborators)

### 1.2 Инструменты качества кода
- [x] Backend: `uv`, Python 3.12, `ruff` (lint + format), `mypy --strict`, `pytest` + `pytest-asyncio`
- [x] Frontend: **npm** (вместо pnpm, см. ADR-003 в [ARCHITECTURE.md](../../ARCHITECTURE.md)), `eslint`, `prettier`, `tsc --noEmit`
- [x] `pre-commit`: базовые проверки файлов, ruff, prettier, **gitleaks** (поиск секретов)

### 1.3 docker-compose

| Сервис | Образ | Порт на хосте | Назначение |
|---|---|---|---|
| `app-db` | `postgres:17` | 5442 | БД приложения и checkpoints LangGraph |
| `target-db` | `postgres:17` | 5443 | Демо-БД для вопросов (роль 2) |
| `qdrant` | `qdrant/qdrant:v1.19.2` | 6333 | Векторный индекс схемы |
| `backend` | `./backend` | 8000 | FastAPI |
| `frontend` | `./frontend` | 3000 | Next.js (standalone) |
| `langfuse-web` + worker, postgres, clickhouse, redis, minio | официальные образы Langfuse v4 | 3001 (UI), 9090 (MinIO) | Трассировка |

- [x] Volumes для данных, healthcheck у каждого сервиса, `depends_on: condition: service_healthy`
- [x] Langfuse: в роли 5 по умолчанию Langfuse Cloud (ADR-013), self-hosted — профиль `langfuse-local` (`make up-langfuse`) в отдельном файле [`infra/langfuse/docker-compose.yml`](../../infra/langfuse/docker-compose.yml), подключён через `include`. Организация, проект и API-ключи создаются автоматически при первом запуске
- [x] Все порты привязаны к `127.0.0.1`, хост-порты переопределяются в `.env` (5432 часто занят локальным Postgres)
- [ ] `docker-compose.override.yml` с hot reload — отложено до роли 3, пока разработка идёт локально через `uv run uvicorn --reload` и `npm run dev`

### 1.4 Конфигурация
- [x] [`.env.example`](../../.env.example) + [`scripts/init-env.sh`](../../scripts/init-env.sh): `make env` создаёт `.env` со случайными секретами (`chmod 600`)
- [x] Backend читает конфиг через `pydantic-settings` ([`app/core/config.py`](../../backend/app/core/config.py)). Если обязательной переменной нет, приложение падает при старте (есть тест)

### 1.5 Makefile
- [x] `help`, `env`, `up`, `up-lite`, `down`, `ps`, `logs`, `test`, `lint`, `format`
- [x] Заглушки `seed`, `index`, `eval-smoke` (реализуются в ролях 2, 5 и 7)

### 1.6 CI (GitHub Actions)
- [x] `backend.yml`: ruff → mypy → pytest. Сервис postgres добавится в роли 3 вместе с тестами БД
- [x] `frontend.yml`: lint → prettier → typecheck → build
- [x] `compose.yml`: генерация `.env` → `docker compose config` → сборка образов backend и frontend
- [ ] `evals.yml` (роль 7): `make eval-smoke` на PR, ключи LLM в GitHub Secrets

### 1.7 Деплой (опционально, к апрелю)
- [ ] VPS или Railway/Render, HTTPS, отдельные секреты для prod. Публичный URL для демонстрации на защите

## Definition of Done
- [x] `make up` на чистой машине поднимает все 11 сервисов, все healthy
- [x] `GET http://localhost:8000/api/health` → `{"status":"ok"}`, фронтенд отдаёт 200, Langfuse отвечает на `/api/public/health` и принимает сгенерированные ключи
- [ ] CI зелёный на `main` (проверить после первого push)
- [x] В истории git нет личных файлов и секретов (gitleaks в pre-commit)

## База знаний
- `ai_engineering.md` §10 (LLMOps: LangSmith или Langfuse, self-hosted)
- `ai_security.md` §2.2 (секреты только через env)
