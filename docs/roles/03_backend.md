# Role 3. Backend

**Status: ✅ completed** (October 2026)

**Aim:** a FastAPI service with all endpoints from [`CONTRACTS.md`](../CONTRACTS.md). For now a stub works in place of the agent and returns a correct SSE stream.
**Depends on:** roles 1 and 2.
**Needed for:** SQL Validator (schema introspection, connection pools), AI Agent (the place where the graph is started), Frontend (API).

## Structure

```text
backend/app/
├── main.py              # create_app(): error handlers, logging, CORS, routers, lifespan
├── bootstrap.py         # at startup: first admin from env, registration of the demo database
├── core/                # config, db (async SQLAlchemy), errors, logging, security
├── models/              # application database tables (role 2)
├── schemas/
│   ├── api.py           # REST requests and responses
│   ├── agent.py         # agent events and their payloads (CONTRACTS §2–3), shared by roles 4–5
│   └── schema_snapshot.py
├── services/
│   ├── target_db.py     # connection to the user's database: privilege check, introspection, pools
│   ├── datasources.py   # registration and indexing of sources
│   ├── indexer.py       # SchemaIndexer interface (implemented in role 5)
│   └── chat.py          # dialogue turn: agent events → SSE, saving the answer and the log
├── agent/
│   ├── runner.py        # AgentRunner interface
│   └── fake.py          # FakeAgentRunner
└── api/                 # auth, datasources, sessions, messages, health, deps
```

## Tasks

### 3.1 Skeleton
- [x] Async SQLAlchemy + asyncpg, a `DbSession` dependency, correct closing of the pools in lifespan
- [x] A single error format `{error: {code, message}}`, including 404 for an unknown path and validation errors (`details`)
- [x] Structured `structlog` logs with `request_id` (the `x-request-id` header); JSON in production, readable output in development

### 3.2 Authentication
- [x] Registration (role `analyst`), login with JSON `{email, password}`, `GET /auth/me`
- [x] `pwdlib` (Argon2), JWT (PyJWT, HS256, TTL 24 h). For an unknown email a dummy hash is checked so that the response time does not reveal whether the user exists
- [x] `CurrentUser` and `AdminUser` dependencies. Swagger has an Authorize button (HTTP Bearer)
- [x] The first `admin` is created from `ADMIN_EMAIL` / `ADMIN_PASSWORD` at startup

### 3.3 Data sources
- [x] Check of the connection and of the **role privileges** in the system catalogs. The original plan used a test `CREATE TEMP TABLE`, but the role 2 tests showed that with `default_transaction_read_only` turned on it fails even for a role with write privileges. Checked: superuser attributes, `CREATE`/`TEMP` on the database, `CREATE` in schemas, `INSERT/UPDATE/DELETE/TRUNCATE` on tables, the `pg_*_server_files` roles. The error lists the specific violations
- [x] The connection string is stored encrypted (Fernet, `APP_ENCRYPTION_KEY`)
- [x] Introspection → `SchemaSnapshot`: tables and views, types (`format_type`), PKs, FKs (`schema.table.column`), comments, estimated row count, database time zone
- [x] `sample_values`: all values of a text column if there are ≤ 20. Candidates are selected by `pg_stats.n_distinct` (taking negative values into account: −1 means "all unique"), and the values are read with `SELECT DISTINCT` with a 2 s timeout. Originally a list of frequent values from `pg_stats` was planned, but it is empty for lookup tables with unique values (`regions.name`), and these are exactly the ones needed to match "Almaty" with "Almaty region"
- [x] Indexing in the background (an `asyncio` task), status `indexing → ready | error`. A `SchemaIndexer` interface with an empty implementation (Qdrant comes in role 5)
- [x] A connection pool per source (`TargetPools`), closed when the source is deleted and when the application stops
- [x] The demo database is registered automatically at startup (`DEMO_DATASOURCE_URL`). If the demo database is not filled yet, startup does not fail, and the log suggests `make seed`

### 3.4 Sessions and messages
- [x] Session CRUD. Other users' sessions return 404, not 403, so as not to reveal that they exist
- [x] `POST /sessions/{id}/messages` and `/clarify` return SSE (`fastapi.sse`). The response is built by hand, not through a generator endpoint, so that the checks before the stream return ordinary HTTP errors
- [x] `FakeAgentRunner`: a normal answer, a clarification (a question with the word "продаж", "sales"), a refusal ("удали" (delete), "drop"…)
- [x] The `AgentRunner.run / resume` interface. The stub is connected through `get_runner()`; in role 5 the LangGraph agent replaces it
- [x] When the stream ends, the assistant message (SQL, validator report, result, chart, clarification, `trace_id`) and a `query_log` record are saved. `message_id` is put into `done`
- [x] One active stream per session (`session_busy`). Until the clarification is answered, a new question is not accepted (`clarification_pending`)
- [x] An agent error turns into an `error` + `done` event, not a dropped connection. The session is released even if the client disconnects
- [x] The session title is the first question (up to 80 characters)

### 3.5 Feedback
- [x] `POST /messages/{id}/feedback`: only for assistant answers in one's own session; a repeated rating replaces the previous one (`ON CONFLICT DO UPDATE`)
- [ ] Sending the score to Langfuse by `trace_id`, in role 5

### 3.6 Tests
- [x] 31 tests: auth, JWT, encryption, data sources (on a specially created target database with "read" and "read + INSERT" roles), sessions, SSE scenarios, clarification, refusal, agent failure, privacy, feedback, bootstrap, migrations
- [x] Coverage 97% (CI threshold 80%). Greenlet tracking is enabled in coverage: without it, lines after `await` in async SQLAlchemy were not counted

## Definition of Done
- [x] All endpoints from CONTRACTS §1 work, and Swagger at `/docs` is up to date
- [x] The demo database is connected automatically, and `GET /datasources/{id}/schema` returns 11 tables with comments, FKs and sample values
- [x] A connection with a writing role and with a superuser is rejected with a list of violations
- [x] The SSE stub passes all scenarios from CONTRACTS §2, including `clarification` → `/clarify`
- [x] Coverage of `api/` and `services/` ≥ 70% (actually 93–100%)

## Knowledge base
- `prompting_memory_tools.md` §4.1 (just-in-time: the schema and sample values instead of all the data)
- `ai_security.md` §2.3 (values from the database and column comments are untrusted data)
- `ai_engineering.md` §7 (HITL: pausing the graph and resuming on the user's answer; here, the API part)
