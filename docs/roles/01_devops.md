# Role 1. DevOps

**Status: ✅ completed** (October 2026)

**Aim:** an environment where the whole project starts with one command and code quality is checked automatically.
**Depends on:** nothing.
**Needed for:** all other roles.

## Tasks

### 1.1 Repository
- [x] Branch `main`, private repository https://github.com/Abegerov4/Suhbat2DB
- [x] Monorepository structure: `backend/`, `frontend/`, `infra/`, `scripts/`, `docs/` (`evals/` and `demo_db/` appear in roles 2 and 7)
- [x] `.gitignore`: personal materials, `.env`, Python and Node artefacts. Checked that personal documents and course materials do not get into the index
- [ ] GitHub Projects: a `Backlog / In progress / Review / Done` board with the tasks from the role files (done by hand in the GitHub web interface)
- [ ] Supervisor access to the repository (Settings → Collaborators)

### 1.2 Code quality tools
- [x] Backend: `uv`, Python 3.12, `ruff` (lint + format), `mypy --strict`, `pytest` + `pytest-asyncio`
- [x] Frontend: **npm** (instead of pnpm, see ADR-003 in [ARCHITECTURE.md](../../ARCHITECTURE.md)), `eslint`, `prettier`, `tsc --noEmit`
- [x] `pre-commit`: basic file checks, ruff, prettier, **gitleaks** (secret detection)

### 1.3 docker-compose

| Service | Image | Host port | Purpose |
|---|---|---|---|
| `app-db` | `postgres:17` | 5442 | Application database and LangGraph checkpoints |
| `target-db` | `postgres:17` | 5443 | Demo database for questions (role 2) |
| `qdrant` | `qdrant/qdrant:v1.19.2` | 6333 | Vector index of the schema |
| `backend` | `./backend` | 8000 | FastAPI |
| `frontend` | `./frontend` | 3000 | Next.js (standalone) |
| `langfuse-web` + worker, postgres, clickhouse, redis, minio | official Langfuse v4 images | 3001 (UI), 9090 (MinIO) | Tracing |

- [x] Volumes for data, a healthcheck on every service, `depends_on: condition: service_healthy`
- [x] Langfuse: since role 5 Langfuse Cloud is the default (ADR-013); self-hosted is the `langfuse-local` profile (`make up-langfuse`) in a separate file [`infra/langfuse/docker-compose.yml`](../../infra/langfuse/docker-compose.yml), connected through `include`. The organisation, project and API keys are created automatically on the first start
- [x] All ports are bound to `127.0.0.1`, and host ports can be overridden in `.env` (5432 is often taken by a local Postgres)
- [ ] `docker-compose.override.yml` with hot reload, postponed until role 3 while development runs locally through `uv run uvicorn --reload` and `npm run dev`

### 1.4 Configuration
- [x] [`.env.example`](../../.env.example) + [`scripts/init-env.sh`](../../scripts/init-env.sh): `make env` creates `.env` with random secrets (`chmod 600`)
- [x] The backend reads the configuration through `pydantic-settings` ([`app/core/config.py`](../../backend/app/core/config.py)). If a required variable is missing, the application fails at startup (there is a test)

### 1.5 Makefile
- [x] `help`, `env`, `up`, `up-lite`, `down`, `ps`, `logs`, `test`, `lint`, `format`
- [x] Stubs `seed`, `index`, `eval-smoke` (implemented in roles 2, 5 and 7)

### 1.6 CI (GitHub Actions)
- [x] `backend.yml`: ruff → mypy → pytest. A postgres service is added in role 3 together with the database tests
- [x] `frontend.yml`: lint → prettier → typecheck → build
- [x] `compose.yml`: `.env` generation → `docker compose config` → build of the backend and frontend images
- [ ] `evals.yml` (role 7): `make eval-smoke` on pull requests, LLM keys in GitHub Secrets

### 1.7 Deployment (optional, by April)
- [ ] A VPS or Railway/Render, HTTPS, separate secrets for production. A public URL for the demonstration at the defence

## Definition of Done
- [x] `make up` on a clean machine starts all 11 services, all of them healthy
- [x] `GET http://localhost:8000/api/health` → `{"status":"ok"}`, the frontend returns 200, Langfuse answers on `/api/public/health` and accepts the generated keys
- [ ] CI is green on `main` (to be checked after the first push)
- [x] The git history contains no personal files or secrets (gitleaks in pre-commit)

## Knowledge base
- `ai_engineering.md` §10 (LLMOps: LangSmith or Langfuse, self-hosted)
- `ai_security.md` §2.2 (secrets only through env)
