# Contracts between Suhbat2DB components

This file is the single source of truth for the interfaces between roles. The code must match it. If they differ, this file is updated first.

---

## 1. REST API

Base prefix: `/api`. Authentication: `Authorization: Bearer <JWT>`. User roles: `admin`, `analyst`.

The browser does not call the API directly but goes through Next.js (Backend for Frontend, [ADR-017](../ARCHITECTURE.md#adr-017-backend-for-frontend-and-jwt-in-an-httponly-cookie)): the frontend `POST /api/auth/login` puts the token into an httpOnly cookie, `POST /api/auth/logout` removes it, and all other `/api/*` paths are proxied to FastAPI with the `Authorization` header.

| Method | Path | Role | Request body | Response |
|---|---|---|---|---|
| GET | `/health` | — | — | `{status: "ok"}` |
| POST | `/auth/register` | — | `{email, password}` | `{id, email, role}` |
| POST | `/auth/login` | — | `{email, password}` | `{access_token, token_type: "bearer"}` |
| GET | `/auth/me` | any | — | `{id, email, role}` |
| GET | `/datasources` | any | — | `[Datasource]` |
| POST | `/datasources` | admin | `{name, connection_url}` | `Datasource` (status `indexing`) |
| GET | `/datasources/{id}/schema` | any | — | `SchemaSnapshot` |
| POST | `/datasources/{id}/reindex` | admin | — | `202` + `Datasource` |
| DELETE | `/datasources/{id}` | admin | — | `204` |
| GET | `/sessions` | any | — | `[Session]` |
| POST | `/sessions` | any | `{datasource_id, title?}` | `Session` |
| GET | `/sessions/{id}/messages` | owner | — | `[Message]` |
| POST | `/sessions/{id}/messages` | owner | `{content}` (1–2000 characters) | **SSE stream** (section 2) |
| POST | `/sessions/{id}/clarify` | owner | `{answers: [ClarificationAnswer]}` | **SSE stream** (the graph continues) |
| POST | `/sessions/{id}/stop` | owner | — | `204`; the running turn is cancelled, and the stream ends with `error` (`cancelled`) and `done` |
| POST | `/messages/{id}/feedback` | owner | `{score: 1 \| -1, comment?}` | `204` |
| GET | `/stats?days=14&tz=Asia/Almaty` | any | — | `Stats` (own dialogues only; `days` 1–90, `tz` is an IANA zone) |

```ts
type Datasource = { id: string; name: string; dialect: "postgres"; status: "indexing" | "ready" | "error"; error?: string; indexed_at?: string; tables_count?: number };
type Session = { id: string; datasource_id: string; title: string; created_at: string };
type Message = {
  id: string; role: "user" | "assistant"; content: string; created_at: string;
  sql?: string; validation_report?: ValidationReport; result?: QueryResult;
  chart_spec?: ChartSpec; clarification?: ClarificationRequest; trace_id?: string;
  error?: { code: string; message: string };  // refusal or turn error (restores the refusal card)
};
type Stats = {
  questions: number; answered: number; clarifications: number; refused: number;  // turn = answer | clarification | refusal
  sessions: number; datasources: number; datasources_ready: number;
  queries_ok: number; queries_blocked: number; queries_failed: number; avg_duration_ms: number | null;
  blocked_by_level: { level: 1 | 2 | 3 | 4 | 5; name: string; count: number }[];
  feedback_up: number; feedback_down: number;
  activity: { date: string; questions: number; answered: number; clarifications: number; refused: number }[];
};
type ClarificationAnswer = { ambiguity_id: string; option_id?: string; free_text?: string };
```

Errors are returned as `{error: {code: string, message: string}}` with HTTP codes 400/401/403/404/409/422/500. For `422 validation_error`, `details: [{loc, msg, type}]` is added.

| Code | HTTP | When |
|---|---|---|
| `unauthorized` | 401 | No token, or the token is invalid or expired |
| `invalid_credentials` | 401 | Wrong email or password |
| `forbidden` | 403 | The action is for `admin` only |
| `email_taken` | 409 | The email is already registered |
| `datasource_not_found`, `session_not_found`, `message_not_found` | 404 | The object does not exist or belongs to another user |
| `unsupported_datasource` | 422 | The URL is not `postgresql://` |
| `datasource_unreachable` | 422 | Connection failed |
| `datasource_not_readonly` | 422 | The role has write privileges; `message` lists the violations |
| `schema_not_ready` | 409 | The schema is still being indexed |
| `datasource_not_ready` | 409 | A question to a source whose status is not `ready` |
| `session_busy` | 409 | The agent is still answering in this session |
| `clarification_pending` | 409 | A new question before the clarification is answered |
| `no_pending_clarification` | 409 | `/clarify` without a pending clarification |
| `invalid_clarification` | 422 | Unknown ambiguity or option, and no `free_text` |
| `validation_error` | 422 | The request body failed validation |
| `internal_error` | 500 | Unexpected error |

The read-only check when a source is connected looks at the **role privileges** (superuser, `CREATE`/`TEMP` on the database, `CREATE` in schemas, `INSERT/UPDATE/DELETE/TRUNCATE` on tables, the `pg_*_server_files` roles), not at `default_transaction_read_only`, which a session can turn off itself.

---

## 2. Agent SSE events

The stream is `text/event-stream`. Each event is written as `event: <type>` and `data: <json>`. The agent turn runs on the server independently of the connection ([ADR-019](../ARCHITECTURE.md#adr-019-the-agent-turn-does-not-depend-on-the-connection)): if the client disconnects, the answer is still completed and saved; a turn can be stopped only through `POST /sessions/{id}/stop`. The order of events is not fixed, but the stream **always** ends with the `done` event (`done` also follows `error`). The `message_id` in `done` is the id of the saved assistant message; the API layer fills it in, not the agent.

| `event` | `data` | When |
|---|---|---|
| `step` | `{node: NodeName, status: "started" \| "finished", detail?: string}` | Entering and leaving a graph node |
| `clarification` | `ClarificationRequest` | The graph is paused (`interrupt`), and the stream ends with `done` with `awaiting_clarification: true` |
| `sql` | `{sql: string, attempt: number}` | SQL was generated (including after self-correction) |
| `validation` | `ValidationLevelResult` | Result of each validator level |
| `result` | `QueryResult` | The query was executed |
| `answer` | `{text: string}` | Text explanation (several events are allowed for token streaming) |
| `chart` | `ChartSpec` | Chart specification (if a chart is appropriate) |
| `error` | `{code: string, message: string}` | Fatal error or refusal (`refused`, `unsafe_input`, `max_attempts`, `llm_unavailable`) |
| `done` | `{message_id: string, trace_id?: string, awaiting_clarification: boolean}` | End of the stream |

```ts
type NodeName = "guard_input" | "schema_linking" | "detect_ambiguity" | "clarify" | "generate_sql"
              | "validate_sql" | "self_correct" | "execute" | "explain_and_visualize" | "refuse";

type ClarificationRequest = {
  question: string;                       // overall question to the user
  ambiguities: {
    id: string;
    type: "metric" | "temporal" | "value" | "schema" | "scope";
    span: string;                         // the ambiguous fragment of the question
    options: { id: string; label: string; description?: string }[];  // 2–4 options
  }[];
};

type ChartSpec = {
  type: "bar" | "line" | "pie" | "scatter" | "none";
  x: string; y: string[];                 // column names from QueryResult
  title?: string;
};
```

---

## 3. SQL validator

```python
class ValidationLevelResult(BaseModel):
    level: Literal[1, 2, 3, 4, 5]
    name: Literal["syntax", "readonly_policy", "schema", "explain", "execution"]
    passed: bool
    message: str | None = None        # human-readable reason
    hint: str | None = None           # hint for self-correction (for example, a similar column)
    fatal: bool = False               # True → self-correction is not allowed (policy violation)

class ValidationReport(BaseModel):
    passed: bool
    levels: list[ValidationLevelResult]
    normalized_sql: str | None        # SQL after normalisation and the forced LIMIT

class QueryResult(BaseModel):
    columns: list[ColumnMeta]         # {name, type}
    rows: list[list[Any]]
    row_count: int
    truncated: bool                   # True if SQL_MAX_ROWS was reached
    duration_ms: int
```

Public functions of the `app.validator` module (details in [validator.md](validator.md)):

```python
@dataclass(frozen=True)
class Limits:                         # Limits.from_settings() reads the values from env
    max_rows: int = 1000
    statement_timeout_ms: int = 5000
    max_explain_cost: float = 1_000_000
    cartesian_min_rows: int = 10_000
    max_result_bytes: int = 2_000_000

def validate(sql: str, snapshot: SchemaSnapshot, limits: Limits | None = None) -> ValidationReport
    # levels 1–3 without the database; stops at the first failed level.
    # normalized_sql: without comments, outer LIMIT ≤ max_rows + 1 (the extra row = truncation)

async def explain(sql: str, conn: Conn, limits: Limits) -> ValidationLevelResult            # level 4
async def execute_readonly(sql: str, conn: Conn, limits: Limits) -> QueryResult             # level 5

class ExecutionError(Exception):      # raised by execute_readonly; .result is the level 5 ValidationLevelResult
    result: ValidationLevelResult
```

`Conn` is an `asyncpg.Connection` or a pooled connection (`app.services.target_db.Conn`). `report.normalized_sql` is passed to `explain` and `execute_readonly`.

---

## 4. Schema snapshot

```python
class ColumnInfo(BaseModel):
    name: str; data_type: str; nullable: bool
    comment: str | None
    is_pk: bool; fk: str | None              # "schema.table.column"
    sample_values: list[str] | None          # all values of a text column if there are ≤ 20 (value linking)

class TableInfo(BaseModel):
    schema_name: str; name: str; comment: str | None
    row_estimate: int
    columns: list[ColumnInfo]

class SchemaSnapshot(BaseModel):
    datasource_id: str
    timezone: str | None                     # database time zone; the agent takes it into account in dates
    tables: list[TableInfo]
    created_at: datetime
```

---

## 5. Agent state (LangGraph)

Implementation: [`backend/app/agent/state.py`](../backend/app/agent/state.py); graph: [graph.md](graph.md).

```python
class AgentState(TypedDict, total=False):
    question: str                               # question of the current turn
    resolved_question: str                      # question + the user's clarifications
    route: str                                  # node decision; route() in graph.py chooses the route
    pending_clarification: dict | None          # clarification request + interpretations of the options
    turn_clarifications: list[Clarification]    # clarifications of this turn
    clarification_rounds: int                   # limit MAX_CLARIFICATION_ROUNDS (2)
    clarifications: Annotated[list[Clarification], add]   # session memory
    linked_schema: str                          # rendered linked schema (for the prompt)
    linked_tables: list[str]
    examples: list[dict]                        # few-shot "question → SQL"
    sql: str | None
    attempts: int                               # limit AGENT_MAX_CORRECTIONS (3)
    feedback: list[Feedback]                    # errors of earlier attempts for self-correction
    normalized_sql: str | None                  # SQL after the validator (with LIMIT)
    result: dict | None                         # QueryResult
    answer: str | None
    chart: dict | None                          # ChartSpec
    error: dict | None                          # {code, message} for a refusal
    history: Annotated[list[Turn], add]         # questions and SQL of earlier turns (follow-up)

class Clarification(TypedDict): span: str; choice: str; interpretation: str
class Feedback(TypedDict): sql: str; level: int; message: str; hint: str | None
```

Fields without a reducer are reset at the start of each turn (`new_turn(question)`); `clarifications` and `history` accumulate within the session. The schema snapshot, the connection pool and the limits are not passed in the state but in the run context (`AgentContext`), so they are not saved in the checkpoint.

The graph `thread_id` equals `session.id`, so one chat corresponds to one stream of checkpoints (PostgreSQL, `AsyncPostgresSaver`). The clarification answer is passed to the graph as `Command(resume=[{ambiguity_id, option_id, free_text}])`.

Refusal codes in the `error` event: `refused` (request to change data), `unsafe_input` (prompt injection), `out_of_scope`, `unsafe_sql` (fatal policy violation), `max_attempts`, `cannot_answer`, `no_connection`, `internal_error`, `cancelled` (the turn was stopped through `/stop`).
