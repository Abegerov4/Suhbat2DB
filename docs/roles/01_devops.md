# Роль 1. DevOps

**Цель:** окружение, в котором весь проект поднимается одной командой, а качество кода проверяется автоматически.
**Зависит от:** ничего.
**Нужно для:** всех остальных ролей.

## Задачи

### 1.1 Репозиторий
- [ ] `git init`, ветка `main`, приватный GitHub-репозиторий с доступом руководителя
- [ ] Структура монорепозитория: `backend/`, `frontend/`, `evals/`, `demo_db/`, `docs/`
- [ ] Перенести `.gitignore` (личные материалы, `.env`, артефакты Python и Node) и проверить, что обоснование, PDF и `база знаний/` не попали в индекс: `git status --ignored`
- [ ] GitHub Projects: доска с колонками `Backlog / In progress / Review / Done`, задачи из файлов ролей

### 1.2 Инструменты качества кода
- [ ] Backend: `uv` (или `poetry`) для зависимостей, `ruff` (lint + format), `mypy`, `pytest`
- [ ] Frontend: `pnpm`, `eslint`, `prettier`, `tsc --noEmit`
- [ ] `pre-commit` с ruff, prettier и проверкой на секреты (`detect-secrets` или `gitleaks`)

### 1.3 docker-compose

| Сервис | Образ | Порт | Назначение |
|---|---|---|---|
| `app-db` | `postgres:16` | 5432 | БД приложения и checkpoints LangGraph |
| `target-db` | `postgres:16` | 5433 | Демо-БД для вопросов (роль 2) |
| `qdrant` | `qdrant/qdrant` | 6333 | Векторный индекс схемы |
| `backend` | `./backend` | 8000 | FastAPI |
| `frontend` | `./frontend` | 3000 | Next.js |
| `langfuse` | по официальному compose Langfuse | 3001 | Трассировка |

- [ ] Volume для данных Postgres и Qdrant, healthcheck у каждого сервиса, `depends_on: condition: service_healthy`
- [ ] Langfuse: self-host v3 требует дополнительных сервисов (ClickHouse, Redis, S3/MinIO). Брать их из официального compose. Если окружение получается слишком тяжёлым для ноутбука, на время разработки допустим Langfuse Cloud (free tier), а self-host использовать для демо. Решение зафиксировать в `ARCHITECTURE.md`
- [ ] `docker-compose.override.yml` для разработки (hot reload backend и frontend)

### 1.4 Конфигурация
- [ ] `.env.example` со всеми переменными из README (раздел «Запуск») без значений
- [ ] Backend читает конфиг через `pydantic-settings`. Если обязательная переменная отсутствует, приложение падает при старте

### 1.5 Makefile
```make
up          # docker compose up -d --build
down        # docker compose down
logs        # docker compose logs -f backend
test        # pytest + pnpm test
lint        # ruff, mypy, eslint, tsc
seed        # заполнить target-db (роль 2)
index       # проиндексировать схему демо-БД в Qdrant (роль 5)
eval-smoke  # быстрый прогон evals (роль 7)
```

### 1.6 CI (GitHub Actions)
- [ ] `backend.yml`: ruff → mypy → pytest (с сервисом postgres)
- [ ] `frontend.yml`: lint → typecheck → build
- [ ] `evals.yml` (подключить в роли 7): `make eval-smoke` на PR, результат публикуется комментарием в PR. Ключи LLM хранятся в GitHub Secrets

### 1.7 Деплой (опционально, к апрелю)
- [ ] VPS или Railway/Render, HTTPS, отдельные секреты для prod. Публичный URL для демонстрации на защите

## Definition of Done
- `make up` на чистой машине поднимает все сервисы, и они проходят healthcheck
- `GET http://localhost:8000/api/health` возвращает `{"status":"ok"}` (заглушка FastAPI), `http://localhost:3000` открывает заглушку Next.js
- CI зелёный на `main`
- В истории git нет личных файлов и секретов

## База знаний
- `ai_engineering.md` §10 (LLMOps: LangSmith или Langfuse, self-hosted)
- `ai_security.md` §2.2 (секреты только через env)
