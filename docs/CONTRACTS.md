# Контракты между компонентами Suhbat2DB

Единый источник правды для интерфейсов между ролями. Код должен соответствовать этому файлу. При расхождении сначала обновляется этот файл.

---

## 1. REST API

Базовый префикс: `/api`. Аутентификация: `Authorization: Bearer <JWT>`. Роли пользователей: `admin`, `analyst`.

| Метод | Путь | Роль | Тело запроса | Ответ |
|---|---|---|---|---|
| GET | `/health` | — | — | `{status: "ok"}` |
| POST | `/auth/register` | — | `{email, password}` | `{id, email, role}` |
| POST | `/auth/login` | — | `{email, password}` | `{access_token, token_type: "bearer"}` |
| GET | `/auth/me` | any | — | `{id, email, role}` |
| GET | `/datasources` | any | — | `[Datasource]` |
| POST | `/datasources` | admin | `{name, connection_url}` | `Datasource` (статус `indexing`) |
| GET | `/datasources/{id}/schema` | any | — | `SchemaSnapshot` |
| POST | `/datasources/{id}/reindex` | admin | — | `202` + `Datasource` |
| DELETE | `/datasources/{id}` | admin | — | `204` |
| GET | `/sessions` | any | — | `[Session]` |
| POST | `/sessions` | any | `{datasource_id, title?}` | `Session` |
| GET | `/sessions/{id}/messages` | owner | — | `[Message]` |
| POST | `/sessions/{id}/messages` | owner | `{content}` (1–2000 символов) | **SSE-поток** (раздел 2) |
| POST | `/sessions/{id}/clarify` | owner | `{answers: [ClarificationAnswer]}` | **SSE-поток** (продолжение графа) |
| POST | `/messages/{id}/feedback` | owner | `{score: 1 \| -1, comment?}` | `204` |

```ts
type Datasource = { id: string; name: string; dialect: "postgres"; status: "indexing" | "ready" | "error"; error?: string; indexed_at?: string; tables_count?: number };
type Session = { id: string; datasource_id: string; title: string; created_at: string };
type Message = {
  id: string; role: "user" | "assistant"; content: string; created_at: string;
  sql?: string; validation_report?: ValidationReport; result?: QueryResult;
  chart_spec?: ChartSpec; clarification?: ClarificationRequest; trace_id?: string;
};
type ClarificationAnswer = { ambiguity_id: string; option_id?: string; free_text?: string };
```

Ошибки возвращаются в формате `{error: {code: string, message: string}}` с HTTP-кодами 400/401/403/404/409/422/500. Для `422 validation_error` добавляется `details: [{loc, msg, type}]`.

| Код | HTTP | Когда |
|---|---|---|
| `unauthorized` | 401 | Нет токена, токен недействителен или просрочен |
| `invalid_credentials` | 401 | Неверный email или пароль |
| `forbidden` | 403 | Действие только для `admin` |
| `email_taken` | 409 | Email уже зарегистрирован |
| `datasource_not_found`, `session_not_found`, `message_not_found` | 404 | Объект не существует или принадлежит другому пользователю |
| `unsupported_datasource` | 422 | URL не `postgresql://` |
| `datasource_unreachable` | 422 | Не удалось подключиться |
| `datasource_not_readonly` | 422 | У роли есть права на запись; в `message` перечислены нарушения |
| `schema_not_ready` | 409 | Схема ещё индексируется |
| `datasource_not_ready` | 409 | Вопрос к источнику, который не в статусе `ready` |
| `session_busy` | 409 | Агент ещё отвечает в этой сессии |
| `clarification_pending` | 409 | Новый вопрос до ответа на уточнение |
| `no_pending_clarification` | 409 | `/clarify` без ожидающего уточнения |
| `invalid_clarification` | 422 | Неизвестная неоднозначность или вариант, и нет `free_text` |
| `validation_error` | 422 | Тело запроса не прошло валидацию |
| `internal_error` | 500 | Непредвиденная ошибка |

Проверка «только чтение» при подключении источника смотрит на **права роли** (суперпользователь, `CREATE`/`TEMP` на базу, `CREATE` в схемах, `INSERT/UPDATE/DELETE/TRUNCATE` на таблицы, роли `pg_*_server_files`), а не на `default_transaction_read_only`, который сессия может отключить сама.

---

## 2. SSE-события агента

Поток `text/event-stream`. Каждое событие записывается как `event: <type>` и `data: <json>`. Порядок событий не фиксирован, но поток **всегда** заканчивается событием `done` (после `error` тоже приходит `done`). `message_id` в `done` — id сохранённого сообщения ассистента; его подставляет API-слой, а не агент.

| `event` | `data` | Когда |
|---|---|---|
| `step` | `{node: NodeName, status: "started" \| "finished", detail?: string}` | Вход и выход из узла графа |
| `clarification` | `ClarificationRequest` | Граф поставлен на паузу (`interrupt`), поток завершается `done` с `awaiting_clarification: true` |
| `sql` | `{sql: string, attempt: number}` | Сгенерирован SQL (в том числе после самокоррекции) |
| `validation` | `ValidationLevelResult` | Результат каждого уровня валидатора |
| `result` | `QueryResult` | Запрос выполнен |
| `answer` | `{text: string}` | Текстовое пояснение (допускается несколько событий для стриминга токенов) |
| `chart` | `ChartSpec` | Спецификация графика (если график уместен) |
| `error` | `{code: string, message: string}` | Фатальная ошибка или отказ (`refused`, `unsafe_input`, `max_attempts`, `llm_unavailable`) |
| `done` | `{message_id: string, trace_id?: string, awaiting_clarification: boolean}` | Конец потока |

```ts
type NodeName = "guard_input" | "schema_linking" | "detect_ambiguity" | "clarify" | "generate_sql"
              | "validate_sql" | "self_correct" | "execute" | "explain_and_visualize" | "refuse";

type ClarificationRequest = {
  question: string;                       // общий вопрос пользователю
  ambiguities: {
    id: string;
    type: "metric" | "temporal" | "value" | "schema" | "scope";
    span: string;                         // фрагмент вопроса, который неоднозначен
    options: { id: string; label: string; description?: string }[];  // 2–4 варианта
  }[];
};

type ChartSpec = {
  type: "bar" | "line" | "pie" | "scatter" | "none";
  x: string; y: string[];                 // имена столбцов из QueryResult
  title?: string;
};
```

---

## 3. Валидатор SQL

```python
class ValidationLevelResult(BaseModel):
    level: Literal[1, 2, 3, 4, 5]
    name: Literal["syntax", "readonly_policy", "schema", "explain", "execution"]
    passed: bool
    message: str | None = None        # человекочитаемая причина
    hint: str | None = None           # подсказка для самокоррекции (например, похожий столбец)
    fatal: bool = False               # True → самокоррекция запрещена (нарушение политики)

class ValidationReport(BaseModel):
    passed: bool
    levels: list[ValidationLevelResult]
    normalized_sql: str | None        # SQL после нормализации и принудительного LIMIT

class QueryResult(BaseModel):
    columns: list[ColumnMeta]         # {name, type}
    rows: list[list[Any]]
    row_count: int
    truncated: bool                   # True, если сработал SQL_MAX_ROWS
    duration_ms: int
```

Публичные функции модуля `app.validator` (подробно — [validator.md](validator.md)):

```python
@dataclass(frozen=True)
class Limits:                         # Limits.from_settings() — значения из env
    max_rows: int = 1000
    statement_timeout_ms: int = 5000
    max_explain_cost: float = 1_000_000
    cartesian_min_rows: int = 10_000
    max_result_bytes: int = 2_000_000

def validate(sql: str, snapshot: SchemaSnapshot, limits: Limits | None = None) -> ValidationReport
    # уровни 1–3 без БД; останавливается на первом непройденном уровне.
    # normalized_sql: без комментариев, внешний LIMIT ≤ max_rows + 1 (лишняя строка = усечение)

async def explain(sql: str, conn: Conn, limits: Limits) -> ValidationLevelResult            # уровень 4
async def execute_readonly(sql: str, conn: Conn, limits: Limits) -> QueryResult             # уровень 5

class ExecutionError(Exception):      # бросает execute_readonly; .result — ValidationLevelResult уровня 5
    result: ValidationLevelResult
```

`Conn` — `asyncpg.Connection` или соединение из пула (`app.services.target_db.Conn`). В `explain` и `execute_readonly` передаётся `report.normalized_sql`.

---

## 4. Снимок схемы

```python
class ColumnInfo(BaseModel):
    name: str; data_type: str; nullable: bool
    comment: str | None
    is_pk: bool; fk: str | None              # "schema.table.column"
    sample_values: list[str] | None          # все значения текстового столбца, если их ≤ 20 (value linking)

class TableInfo(BaseModel):
    schema_name: str; name: str; comment: str | None
    row_estimate: int
    columns: list[ColumnInfo]

class SchemaSnapshot(BaseModel):
    datasource_id: str
    timezone: str | None                     # часовой пояс БД: агент учитывает его в датах
    tables: list[TableInfo]
    created_at: datetime
```

---

## 5. Состояние агента (LangGraph)

Реализация — [`backend/app/agent/state.py`](../backend/app/agent/state.py), граф — [graph.md](graph.md).

```python
class AgentState(TypedDict, total=False):
    question: str                               # вопрос текущего хода
    resolved_question: str                      # вопрос + уточнения пользователя
    route: str                                  # решение узла; маршрут выбирает route() в graph.py
    pending_clarification: dict | None          # запрос уточнения + трактовки вариантов
    turn_clarifications: list[Clarification]    # уточнения этого хода
    clarification_rounds: int                   # лимит MAX_CLARIFICATION_ROUNDS (2)
    clarifications: Annotated[list[Clarification], add]   # память сессии
    linked_schema: str                          # отрисованная связанная схема (для промпта)
    linked_tables: list[str]
    examples: list[dict]                        # few-shot «вопрос → SQL»
    sql: str | None
    attempts: int                               # лимит AGENT_MAX_CORRECTIONS (3)
    feedback: list[Feedback]                    # ошибки прошлых попыток для самокоррекции
    normalized_sql: str | None                  # SQL после валидатора (с LIMIT)
    result: dict | None                         # QueryResult
    answer: str | None
    chart: dict | None                          # ChartSpec
    error: dict | None                          # {code, message} для отказа
    history: Annotated[list[Turn], add]         # вопросы и SQL прошлых ходов (follow-up)

class Clarification(TypedDict): span: str; choice: str; interpretation: str
class Feedback(TypedDict): sql: str; level: int; message: str; hint: str | None
```

Поля без reducer сбрасываются в начале каждого хода (`new_turn(question)`); `clarifications` и `history` накапливаются в пределах сессии. Снимок схемы, пул соединений и лимиты передаются не в состоянии, а в контексте прогона (`AgentContext`): они не сохраняются в checkpoint.

`thread_id` графа совпадает с `session.id`, поэтому один чат соответствует одному потоку checkpoint'ов (PostgreSQL, `AsyncPostgresSaver`). Ответ на уточнение передаётся в граф как `Command(resume=[{ambiguity_id, option_id, free_text}])`.

Коды отказов в событии `error`: `refused` (просьба изменить данные), `unsafe_input` (prompt injection), `out_of_scope`, `unsafe_sql` (фатальное нарушение политики), `max_attempts`, `cannot_answer`, `no_connection`, `internal_error`.
