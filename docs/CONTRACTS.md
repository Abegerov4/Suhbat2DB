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
| POST | `/datasources/{id}/reindex` | admin | — | `Datasource` |
| DELETE | `/datasources/{id}` | admin | — | `204` |
| GET | `/sessions` | any | — | `[Session]` |
| POST | `/sessions` | any | `{datasource_id, title?}` | `Session` |
| GET | `/sessions/{id}/messages` | owner | — | `[Message]` |
| POST | `/sessions/{id}/messages` | owner | `{content}` | **SSE-поток** (раздел 2) |
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

Ошибки возвращаются в формате `{error: {code: string, message: string}}` с HTTP-кодами 400/401/403/404/409/422/500.

---

## 2. SSE-события агента

Поток `text/event-stream`. Каждое событие записывается как `event: <type>` и `data: <json>`. Порядок событий не фиксирован, но поток **всегда** заканчивается событием `done` или `error`.

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

Публичные функции модуля `app.validator`:

```python
def validate(sql: str, schema: SchemaSnapshot, *, dialect: str = "postgres") -> ValidationReport  # уровни 1–3
async def explain(sql: str, conn: AsyncConnection, limits: Limits) -> ValidationLevelResult          # уровень 4
async def execute_readonly(sql: str, conn: AsyncConnection, limits: Limits) -> QueryResult           # уровень 5
```

---

## 4. Снимок схемы

```python
class ColumnInfo(BaseModel):
    name: str; data_type: str; nullable: bool
    comment: str | None
    is_pk: bool; fk: str | None              # "table.column"
    sample_values: list[str] | None          # только для категориальных столбцов (≤ 20 значений)

class TableInfo(BaseModel):
    schema_name: str; name: str; comment: str | None
    row_estimate: int
    columns: list[ColumnInfo]

class SchemaSnapshot(BaseModel):
    datasource_id: str
    tables: list[TableInfo]
    created_at: datetime
```

---

## 5. Состояние агента (LangGraph)

```python
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    datasource_id: str
    question: str
    resolved_question: str
    clarifications: Annotated[list[dict], add]
    clarification_rounds: int                  # лимит 2
    linked_schema: dict                        # подмножество SchemaSnapshot + few-shot примеры
    sql: str | None
    validation_report: ValidationReport | None
    attempts: int                              # лимит AGENT_MAX_CORRECTIONS (3)
    result: QueryResult | None
    answer: str | None
    chart_spec: dict | None
    error: dict | None
```

`thread_id` графа совпадает с `session.id`, поэтому один чат соответствует одному потоку checkpoint'ов.
