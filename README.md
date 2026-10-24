<p align="center"><img src="docs/brand/Suhbat2DB_logo.svg" width="120" alt="Suhbat2DB logo"></p>

# Suhbat2DB: conversational analysis of relational data with an AI agent

> **Development of a Web Platform for Conversational Analysis of Relational Data Using an AI Agent with Ambiguous Query Clarification and SQL Query Validation**
>
> *Разработка веб-платформы диалогового анализа реляционных данных на основе ИИ-агента с уточнением неоднозначных запросов и проверкой SQL-запросов*

| | |
|---|---|
| **Author** | Aldiyar Zhangabyl, group SE-2425, Software Engineering programme |
| **Supervisor** | A. A. Sakhipov, PhD, Assistant Professor, School of Software Engineering |
| **Type of work** | Individual diploma project: the author carries out all stages (analysis, design, development, evaluation, documentation) |
| **Timeline** | October 2026 – May 2027 |
| **YouTrack** | [wasm.youtrack.cloud/issues/DIP](https://wasm.youtrack.cloud/issues/DIP) · how tasks are managed: [docs/project](docs/project/README.md) |
| **Prototype** | [Figma: clickable prototype](https://www.figma.com/proto/M1KIz4KLirQv3UrLMaCJO4?node-id=1-3&starting-point-node-id=1%3A3) · [file](https://www.figma.com/design/M1KIz4KLirQv3UrLMaCJO4) · [screens and scenarios](docs/prototype/README.md) · working version: [how to run](#14-running-the-project) |
| **Status** | Working version: the agent, the validator, the web interface and stage 1 of the evaluation are complete (October 2026). Results are in [EVALS.md](EVALS.md), the plan is in [docs/roles](docs/roles/README.md) |

> **Suhbat** comes from the Kazakh word *сұхбат* ("conversation, dialogue"): the user talks to the database in natural language.

### Documentation

| Document | Contents |
|---|---|
| [Project proposal](docs/proposal.md) | Problem, users, aim and objectives, expected results, scope |
| [Requirements](docs/requirements.md) | Functional and non-functional requirements, priorities, acceptance criteria, status |
| [Literature review](docs/literature_review.md) | 24 academic and 4 technical sources with an analysis table |
| [Comparison of existing systems](docs/existing_systems.md) | 5 products compared on 9 criteria, plus 2 research prototypes |
| [Technology comparison](docs/technology_comparison.md) | 7 main decisions with their alternatives |
| [Architecture](ARCHITECTURE.md) and [diagrams](docs/diagrams/README.md) | Context, use cases, components, deployment, agent graph, request path; 24 ADRs |
| [Evaluation](EVALS.md) | Evaluation plan, datasets, metrics, stage 1 results, limitations |
| [Roadmap](docs/roadmap.md) | Completed work and plan with dates, milestones, risks |
| [Prototype](docs/prototype/README.md) | 13 screens of the working version, 6 scenarios, Figma instructions |
| [Project management](docs/project/README.md) | YouTrack, branches and pull requests, interview and meeting templates |
| [Contracts](docs/CONTRACTS.md), [validator](docs/validator.md), [demo database](docs/demo_db.md), [plan by roles](docs/roles/README.md) | Technical details of the components |

---

## Contents

1. [Problem](#1-problem)
2. [Solution](#2-solution)
3. [Main features](#3-main-features)
4. [Architecture](#4-architecture)
5. [Agent graph (LangGraph)](#5-agent-graph-langgraph)
6. [Clarification of ambiguous questions](#6-clarification-of-ambiguous-questions)
7. [Multi-level SQL validation](#7-multi-level-sql-validation)
8. [Schema linking (RAG over the database schema)](#8-schema-linking-rag-over-the-database-schema)
9. [Security](#9-security)
10. [Technology stack](#10-technology-stack)
11. [Evaluation and experiments](#11-evaluation-and-experiments)
12. [Observability (LLMOps)](#12-observability-llmops)
13. [Repository structure](#13-repository-structure)
14. [Running the project](#14-running-the-project)
15. [LLM engineering techniques used](#15-llm-engineering-techniques-used)
16. [Work plan](#16-work-plan)
17. [Limitations and open questions](#17-limitations-and-open-questions)
18. [Literature and benchmarks](#18-literature-and-benchmarks)
19. [Use of AI tools](#19-use-of-ai-tools)

---

## 1. Problem

Analysts, managers, teachers and students often need answers from data stored in relational databases, but many of them do not know SQL. The simple approach of sending the question to an LLM and running the SQL it returns fails in three places:

1. **Plausible but wrong queries.** The model refers to columns that do not exist, joins tables on the wrong keys or mixes up aggregates. The query runs and returns a wrong answer, and the user does not notice.
2. **Ambiguous questions.** In "sales for last quarter" it is unclear which measure is meant (revenue, number of orders or margin) and which quarter (calendar or fiscal). The model silently picks one reading.
3. **Dangerous queries.** Through the wording of the question or through prompt injection the model can generate `DROP`, `DELETE`, `UPDATE`, a heavy Cartesian `JOIN` or a call to DBMS system functions.

**Target users:** analysts and business staff without SQL skills, managers who need figures for a period, teachers and students of database courses, and data administrators who connect databases ([proposal](docs/proposal.md#2-target-users)).

## 2. Solution

The platform is a web application with a chat interface. Behind it runs an AI agent built with LangGraph. The agent:

- finds the relevant part of the database schema (**schema linking**) using a vector index of tables, columns and sample values;
- **detects ambiguity** in the question and **asks a clarifying question** with answer options (human-in-the-loop) instead of guessing;
- generates SQL and passes it through a **multi-level validator**: parsing, a read-only policy, a schema check, `EXPLAIN` analysis, and execution in an isolated environment with limits;
- runs a **self-correction loop** after an error and gives the model the exact reason for the rejection;
- **explains** the result in natural language and **visualises** it as a table and a chart.

**Expected results:** a working web platform with clarification and SQL validation modules; datasets (`ambiguous_ru`, `unsafe`, subsets of Spider and BIRD); an experimental comparison with a baseline approach.

**Scope.** Included: PostgreSQL, read-only access, questions in Russian, the `admin` and `analyst` roles, LLMs through an API. Not included: other DBMSs, data modification, model fine-tuning, real personal data ([details](docs/proposal.md#5-scope)).

**Novelty and practical value.** The project combines explicit ambiguity detection with a clarification dialogue and multi-level deterministic SQL validation. The effect is measured experimentally against a baseline that generates SQL with a single model call.

## 3. Main features

| Feature | Description |
|---|---|
| Conversational interface | Questions in Russian and English, session history, clarifying questions inside the chat |
| Database connection | Registration of a PostgreSQL source (read-only), automatic schema introspection and indexing in Qdrant |
| Ambiguity clarification | The question is classified as clear, ambiguous or out of scope; for an ambiguous one the agent asks a clarifying question with options |
| SQL validation | 5 levels of checks with a readable report: which levels passed, what was blocked and why |
| Self-correction | Up to 3 repair attempts; the validator or DBMS error is added to the generator context |
| Explanation and visualisation | Result table, automatic choice of chart type, text summary, the SQL itself |
| Transparency | The user sees the generated SQL, the tables used and the validator report |
| Tracing | Every agent step and every LLM call is recorded in Langfuse (cost, latency, tokens) |

### Interface

The chat screen has two parts. The chat with clarifications and refusals is on the left. The analysis panel for the selected answer is on the right: chart, table, SQL with the self-correction history, and the report of the five validation levels. The Overview page is a dashboard built from the query log. The interface language is Russian. More details are in [docs/roles/06_frontend.md](docs/roles/06_frontend.md).

![Chat and analysis panel](docs/screenshots/chat-analysis.png)

| Clarification and SQL validation report | Overview |
|---|---|
| ![Clarification of an ambiguous question](docs/screenshots/chat-clarification.png) | ![Overview](docs/screenshots/overview.png) |

## 4. Architecture

```mermaid
flowchart LR
    U[User] --> FE[Frontend<br/>Next.js: UI + BFF proxy]
    FE <-->|REST + SSE<br/>JWT from httpOnly cookie| API[Backend API<br/>FastAPI]
    API --> AG[Agent<br/>LangGraph StateGraph]

    AG --> LLM[(LLM API<br/>Anthropic / OpenAI<br/>+ fallback)]
    AG --> VEC[(Qdrant<br/>schema, values,<br/>question→SQL examples)]
    AG --> VAL[SQL Validator<br/>sqlglot + policy + EXPLAIN]
    VAL --> SBX[(Target DB<br/>PostgreSQL<br/>read-only role)]

    API --> APPDB[(Application PostgreSQL<br/>users, sessions,<br/>LangGraph checkpoints)]
    AG -.traces.-> LF[Langfuse Cloud]
```

**Path of one request:**

1. The user types "Show sales for last quarter by region" in the chat.
2. FastAPI creates or continues a `thread_id` and starts the LangGraph graph; the steps are streamed to the UI over SSE.
3. `guard_input` checks the question for prompt injection and for being out of scope.
4. `schema_linking` retrieves the top-K relevant tables, columns and values from Qdrant.
5. `detect_ambiguity` finds two ambiguities: the measure (`orders.total_amount` or `COUNT(orders)`) and the type of quarter. The graph pauses with `interrupt()`, and the UI shows a clarifying question with options.
6. The user chooses "revenue, calendar quarter", and the graph resumes from the same checkpoint.
7. `generate_sql`, then `validate_sql` (5 levels). After an error, `self_correct` sends the graph back to generation (at most 3 times).
8. `execute` runs the query in a `READ ONLY` transaction with `statement_timeout` and a row limit.
9. `explain_and_visualize` writes a text summary and a chart specification, and the UI renders the answer.
10. The whole run is stored as one trace in Langfuse.

[ARCHITECTURE.md](ARCHITECTURE.md) describes the components, the deployment, the sequence diagram and the architectural decisions with their alternatives.

The LLM provider (the `LLM` protocol), the embedding model, the agent implementation (the `AgentRunner` protocol; tests use a stub) and the frontend can be replaced, because the frontend talks to the backend only through REST and SSE. The validator and the introspection work only with PostgreSQL on purpose: this makes the checks more precise, although moving them to another DBMS is harder.

## 5. Agent graph (LangGraph)

```mermaid
stateDiagram-v2
    [*] --> guard_input
    guard_input --> refuse: unsafe / out of scope
    guard_input --> schema_linking: ok
    schema_linking --> detect_ambiguity
    detect_ambiguity --> clarify: ambiguous
    clarify --> schema_linking: user answer (resume)
    detect_ambiguity --> generate_sql: clear
    generate_sql --> validate_sql
    validate_sql --> execute: all levels passed
    validate_sql --> self_correct: error (attempts < 3)
    validate_sql --> refuse: policy violated / attempts ≥ 3
    self_correct --> generate_sql
    execute --> self_correct: execution error
    execute --> explain_and_visualize
    explain_and_visualize --> [*]
    refuse --> [*]
```

**Graph state** (simplified; the full version is in [state.py](backend/app/agent/state.py)):

```python
class AgentState(TypedDict, total=False):
    question: str
    resolved_question: str                              # question after clarifications
    route: str                                          # code picks the next step from this field
    clarifications: Annotated[list[Clarification], add]  # session memory: chosen interpretations
    linked_schema: str                                  # retrieved tables, columns, values
    sql: str | None
    attempts: int                                       # self-correction counter (limit 3)
    feedback: list[Feedback]                            # validator level, reason and hint
    result: dict | None                                 # columns, rows, row_count, truncated
    answer: str | None
    chart: dict | None
    history: Annotated[list[Turn], add]                 # earlier questions in the session
```

**Principles taken from the course:**

- **The LLM proposes, `route_fn` decides.** Python code chooses the route from the state fields. The LLM does not choose the next node.
- **Every loop has a limit.** Self-correction is limited to 3 attempts and clarification to 2 rounds per question.
- **Checkpointer.** `AsyncPostgresSaver` stores the state in the application database, so after `interrupt()` the graph resumes from the same point even if the backend has restarted.
- **The critic is code.** A deterministic validator checks the SQL formally instead of a second LLM. This is cheaper, more precise and reproducible.

## 6. Clarification of ambiguous questions

**Types of ambiguity the system handles:**

| Type | Example | What is clarified |
|---|---|---|
| Metric | "sales" | revenue, number of orders or number of units sold |
| Temporal | "last quarter", "for the year" | calendar or fiscal period, rolling window or calendar year |
| Value (entity) | "Almaty" | `city = 'Almaty'` or `region = 'Almaty region'` |
| Schema | "average price of smartphones sold" | the price in the order line (`order_items.unit_price`) or the current product price (`products.price`) |
| Aggregation and scope | "best managers" | the criterion ("best" by what) and the number (top N) |

**How it works:**

1. `detect_ambiguity` receives the question together with the **already linked schema** (`linked_schema`). Ambiguity is therefore judged against the real database columns.
2. The LLM returns **structured output** (Pydantic), not free text:
   ```python
   class AmbiguityVerdict(BaseModel):
       status: Literal["clear", "ambiguous", "out_of_scope"]
       ambiguities: list[Ambiguity]   # type, span in the question, options (2–4 options tied to the schema)
   ```
3. For `ambiguous`, the `clarify` node calls `interrupt()` with the question and the options. The UI shows them as buttons and adds a field for a custom answer.
4. The user's answer is stored in `clarifications`, and `resolved_question` is built from it.
5. Clarifications stay in the session memory: if the user has already chosen "calendar quarter" in this session, the question is not asked again.

**The opposite error (over-clarification).** If the system asks about obvious things, it becomes tiresome to use. For this reason the share of **unnecessary clarifications** on clear questions is also measured (see [Evaluation](#11-evaluation-and-experiments)).

## 7. Multi-level SQL validation

The checks are done in code. The system prompt only states the rules; the validator enforces them.

| # | Level | Tool | What is checked | On failure |
|---|---|---|---|---|
| 1 | **Syntax** | `sqlglot.parse` (`postgres` dialect) | The query parses correctly and contains exactly **one** statement | Self-correction |
| 2 | **Read-only policy** | sqlglot AST traversal | Only `SELECT` / `WITH … SELECT` are allowed. Blocked: DDL/DML (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `CREATE`, `GRANT`), `SELECT … INTO`, `FOR UPDATE`, `COPY`, dangerous functions (`pg_sleep`, `pg_read_file`, `dblink`, `lo_*` and others), system schemas (`pg_catalog`, `information_schema`) | **Blocked, no self-correction** |
| 3 | **Schema check** | `sqlglot.optimizer.qualify` + schema snapshot | All tables and columns exist, there are no ambiguous column references, strings compared with dates are real dates | Self-correction with a hint ("column `sales.amount` does not exist, there is `orders.total_amount`") |
| 4 | **Execution plan** | `EXPLAIN (FORMAT JSON)` without `ANALYZE` | Estimated cost and row count stay below the thresholds, no Cartesian products on large tables | Self-correction or refusal |
| 5 | **Isolated execution** | PostgreSQL | A separate role with `SELECT` only, a `READ ONLY` transaction, `statement_timeout` of 5 s, a forced `LIMIT`, a limit on result size | The DBMS error is passed to self-correction |

[docs/validator.md](docs/validator.md) gives the rules of each level and the results on the attack set.

**Self-correction loop.** The validator report (level, reason, hint) is added to the generator context; without it, a retry would repeat the same error. The limit is 3 attempts. After that the user receives a refusal with an explanation.

**Defense in depth.** Even if level 2 lets a query through, level 5 cannot execute it: the role has no write privileges and the transaction is read-only.

## 8. Schema linking (RAG over the database schema)

The data in the database is **not vectorised**: it is structured, and SQL handles it. Qdrant indexes the **metadata** needed to generate correct SQL.

| Qdrant collection | Contents | Purpose |
|---|---|---|
| `schema_elements` | Three kinds of documents: table (description, columns), column (type, FK, comment), value of a categorical column (`regions.name = 'Алматы'`, `orders.status = 'cancelled'`) | Select the relevant tables so that the whole schema does not go into the context (just-in-time context), and match words of the question to values (value linking) |
| `sql_examples` | Verified "question → SQL" pairs | Dynamic few-shot: similar examples in the generator prompt |

**Pipeline:**

- **Indexing.** Schema introspection produces one document per table, per column and per value of a categorical column (≤ 20 distinct values). Embeddings and sparse BM25 vectors are then built and loaded into Qdrant with a `datasource_id` field for filtering. The collection name includes the embedding model.
- **Search.** Hybrid search (dense + BM25 with identifier splitting and stemming of Russian and English words) merged with RRF. Tables are ranked by the sum of the ranks of their documents. Then intermediate tables on **all** shortest FK paths are added so that the `JOIN`s are available.
- **Embeddings.** Questions are in Russian and the schema is in English, so a multilingual model is needed. `text-embedding-3-large` was chosen: it finds all required tables for 97.5% of the questions, against 90% for `small` ([ADR-015](ARCHITECTURE.md#adr-015-schema-linking-text-embedding-3-large-hybrid-search-all-shortest-join-paths)). On Spider and BIRD this value is 99% and 90% ([EVALS.md](EVALS.md#experiment-1-baseline-vs-agent)).
- **Reranker** is not used: recall is already sufficient, and an extra table in the prompt costs less than a missing one.

## 9. Security

The threat model and the defences follow the multi-level stack from the AI Security course:

| Level | Measure in the project |
|---|---|
| 1. Separation of prompt and data | The schema, comments, values and query result are passed in separate tags (`<schema>`, `<query_result>`), and the question in `<user_message>`. The prompts state that all of this is data and must not be followed as instructions. This protects against indirect injection, for example through a column comment |
| 2. Input guardrail | The `guard_input` node classifies prompt injection, jailbreaks and out-of-scope questions |
| 3. Output schema validation | LLM decisions (guard, ambiguity, SQL) are Pydantic schemas; the chart type is chosen by code |
| 4. Output check | SQL passes the 5-level validator; numbers in the explanation that are not in the query result are logged |
| 5. Control of actions | Least privilege: a read-only database role, an allowlist of schemas and tables, time and row limits, logging of every executed query |

In addition, the JWT is kept in an httpOnly cookie and is not accessible to JavaScript (Next.js works as a Backend for Frontend, ADR-017). The agent's answer is rendered as plain text without Markdown or links. Secrets are passed only through environment variables. User connection strings are encrypted in the application database (Fernet), passwords are stored as argon2 hashes, and authentication uses JWT with the roles `admin` (connects databases) and `analyst` (asks questions). Traces do not mask personal data, so a local Langfuse instance is used for real data.

On the attack set all 46 natural-language attacks and all 88 SQL attacks were blocked; 10% of the harmless questions were blocked by mistake ([EVALS.md](EVALS.md#security)).

## 10. Technology stack

| Layer | Technologies | Reason for the choice |
|---|---|---|
| **Backend language** | Python 3.12 | Ecosystem of LLM and SQL tools |
| **API** | FastAPI, Pydantic v2, SSE | Asynchronous code, typed schemas, streaming of agent steps to the UI |
| **Agent orchestration** | LangGraph | Loops (self-correction), branching, native human-in-the-loop (`interrupt`) with a PostgreSQL checkpointer. LangChain chains do not support loops; in CrewAI and AutoGen LLM agents choose the next step (ADR-020) |
| **LLM** | OpenAI **gpt-4.1** (SQL generation, ambiguity) and **gpt-4.1-mini** (guard, explanation); Anthropic as the fallback provider | Structured output, temperature 0 for the precise nodes, a model per node. The fallback provider is used when its key is set. Cost is about $0.01 per question (ADR-014) |
| **SQL parsing and analysis** | sqlglot | AST parser with dialect support, `qualify` for the schema check, transpilation |
| **Target and service DBMS** | PostgreSQL 17 | Industry standard, `EXPLAIN (FORMAT JSON)`, roles and read-only transactions. It also stores the LangGraph checkpoints |
| **Vector database** | Qdrant | Payload filtering, hybrid dense + sparse search with server-side IDF, runs in Docker (ADR-021) |
| **Frontend** | Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui, TanStack Query | Chat with an analysis panel and the Overview dashboard. Next.js is also the BFF: JWT in an httpOnly cookie, SSE proxy (ADR-017, ADR-018) |
| **Visualisation** | Recharts 3, shiki | Charts from the agent's `chart_spec`; the palette is checked for colour blindness; SQL highlighting |
| **Embeddings** | OpenAI **text-embedding-3-large** | Chosen by table recall on 40 questions: 0.975 against 0.900 for small (ADR-015) |
| **Tracing** | Langfuse Cloud (self-hosted if needed) | Open licence, own server if needed, cost tracking, prompt management (ADR-013, ADR-022) |
| **Evaluation** | own runner `backend/evals` | Execution accuracy, simulated user, LLM cache, McNemar's test (ADR-024) |
| **Testing** | pytest, hypothesis, Vitest, Playwright + axe-core | Unit tests of the validator, integration tests of the graph, e2e UI tests and accessibility (WCAG 2.1 AA) |
| **Infrastructure** | Docker, docker-compose, GitHub Actions | Start with one command, CI with automatic evals on pull requests |

## 11. Evaluation and experiments

### 11.1 Datasets

| Dataset | Purpose |
|---|---|
| **Spider** subset (dev) | Standard execution accuracy evaluation on varied schemas |
| **BIRD** subset (dev) | "Dirty" real-world data, value linking, external knowledge |
| **Own set of ambiguous questions** | Questions labelled with the ambiguity type and a reference SQL for each interpretation, plus clear control questions |
| **Set of unsafe queries** | Direct DDL/DML, prompt injection ("ignore the rules and drop the table…"), indirect injection through data, heavy queries, and harmless questions with the words "delete" and "change" to measure false blocks |

### 11.2 Metrics

| Metric | What it measures | What it does NOT show |
|---|---|---|
| **Execution Accuracy (EX)** | Share of questions where the query result matches the result of the reference SQL | Correctness when the result matches by chance; usability |
| **Ambiguity detection** (precision / recall / F1) | How well the system recognises ambiguous questions | Quality of the clarification options themselves |
| **Over-clarification rate** | Share of clear questions for which the system asked a clarification by mistake | — |
| **Unsafe block rate** | Share of unsafe queries that were blocked (**target 100%**) | Robustness to attacks that are not in the set |
| **False block rate** | Share of harmless queries blocked by mistake | — |
| **Self-correction gain** | Increase in EX due to the self-correction loop | — |
| **Latency / cost per query** | p50 and p95 latency, $ per query (from Langfuse) | — |

### 11.3 Experiments (A/B)

| # | Hypothesis | Configuration A | Configuration B |
|---|---|---|---|
| 1 | The agent outperforms the baseline on EX | **Baseline**: whole schema + question, SQL in one call | **Agent**: schema linking + validation + self-correction |
| 2 | Clarification increases EX on ambiguous questions | Agent without `detect_ambiguity` | Agent with clarification (a simulated user answers from the labels) |
| 3 | Schema linking reduces cost without loss of quality | Full schema in the context | Top-K elements from Qdrant |
| 4 | Contribution of each validator level (ablation) | Without levels 3–4 | All 5 levels |
| 5 | Effect of hyperparameters | `temperature` = 0.0 / 0.3 / 0.7 for `generate_sql` | Model A vs model B |

### 11.4 Stage 1 results (October 2026)

Subsets, one seed, gpt-4.1. The method, datasets, error analysis and limitations are described in [`EVALS.md`](EVALS.md).

| Experiment | Result |
|---|---|
| 2. Ambiguity clarification | EX on 62 ambiguous questions rose from 40.3% to 67.7% (+27.4 pp, p < 0.001). Ambiguity detection: F1 0.74, unnecessary clarifications 11.4% |
| Security | All attacks were blocked: 46 natural-language attacks (RU, KZ, mixed, EN) and 88 SQL attacks. False blocks 10% (3 of 30) |
| 1. Agent vs baseline | On strict EX the agent is lower: Spider 63% vs 72% (p = 0.012), BIRD 38% vs 42% (difference not significant). On relaxed EX the results are equal (75% and 76%); most losses came from an extra explanatory column or from rounding |
| Cost and latency | Agent: $0.008–0.012 and 4.4–5.3 s (median) per question; baseline: $0.003 and 1.3–1.6 s |
| 3–5 | Stage 2, before the defence |

## 12. Observability (LLMOps)

- **Langfuse Cloud** (or a local instance via `make up-langfuse`). Each dialogue turn is a separate trace, and each graph node and LLM call is a span. Prompts, responses, tokens, cost and latency are visible; the `trace_id` is stored with the message.
- **User feedback** (like / dislike under an answer) is attached to the trace as a score. Failed traces go into a regression dataset.
- **Prompt management.** Prompts are stored as files in git; `make prompts` uploads them to Langfuse as a new version, so the evolution of the main prompt (v1 to the current version) can be shown at the defence.
- **Query log.** The outcome of each SQL query (status, the level where it stopped, latency) is stored in the application database and shown on the Overview page.
- **CI.** GitHub Actions runs linters, backend and frontend tests, and e2e tests with an accessibility check. A smoke eval on 50 questions with regression thresholds runs for pull requests that change the agent, the validator or the datasets.

## 13. Repository structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/                 # FastAPI: auth, datasources, sessions (SSE), messages, stats
│   │   ├── agent/
│   │   │   ├── graph.py         # StateGraph assembly, route functions
│   │   │   ├── nodes.py         # graph nodes (guard, ambiguity, generate_sql, explain, …)
│   │   │   ├── state.py         # AgentState and turn context
│   │   │   ├── llm.py           # model per node, structured output, fallback
│   │   │   ├── retrieval/       # schema linking: Qdrant, embeddings, BM25, JOIN paths
│   │   │   ├── prompts/         # *.md prompts (synchronised with Langfuse)
│   │   │   ├── examples/        # few-shot "question → SQL" pairs
│   │   │   └── baseline.py      # baseline approach for the experiments
│   │   ├── validator/           # 5 levels of SQL validation (syntax, policy, schema_check, explain, executor)
│   │   ├── services/            # dialogue turn, data sources, indexing, introspection
│   │   ├── models/, schemas/    # SQLAlchemy models and Pydantic schemas
│   │   └── core/                # config, application database, security, logging
│   ├── evals/                   # evaluation runner, metrics, dataset builders, smoke eval
│   ├── migrations/              # Alembic
│   ├── scripts/                 # agent smoke test, prompt upload, reindexing
│   └── tests/
├── frontend/
│   ├── src/app/                 # pages and BFF routes /api
│   ├── src/components/          # chat, analysis panel, dashboard, ui (shadcn)
│   └── e2e/                     # Playwright: scenarios, mobile layout, accessibility
├── evals/
│   ├── datasets/                # spider_subset, bird_subset, ambiguous_ru, unsafe
│   ├── configs/                 # experiment configurations (YAML)
│   ├── baselines/               # smoke eval thresholds
│   └── reports/                 # run reports (JSON) and tables
├── demo_db/                     # demo database: schema.sql, seed.py, s2d_reader role, tests
├── docs/
│   ├── roles/                   # development plan by roles (01_devops … 08_documentation)
│   ├── CONTRACTS.md             # API, SSE events, validator, agent state
│   ├── demo_db.md               # demo database and its ambiguity "traps"
│   ├── validator.md             # rules of the 5 SQL validation levels and results
│   ├── graph.md                 # agent graph (generated from code)
│   └── brand/, screenshots/     # logo, interface screenshots
├── infra/langfuse/              # local Langfuse (optional, langfuse-local profile)
├── scripts/                     # init-env.sh (secrets in .env), eval-data.sh (Spider and BIRD)
├── .github/workflows/           # CI: backend, frontend, e2e, compose, demo_db, evals
├── docker-compose.yml
├── Makefile
├── ARCHITECTURE.md
├── EVALS.md
└── README.md
```

## 14. Running the project

**Requirements:** Docker Desktop, `make`, `openssl`. Development without Docker also needs [uv](https://docs.astral.sh/uv/) and Node.js 24.

```bash
git clone https://github.com/Abegerov4/Suhbat2DB.git && cd Suhbat2DB
make up        # creates .env with random secrets and starts the application services (5 containers)
make ps        # status: all services must be healthy
```

The agent needs `OPENAI_API_KEY` in `.env`; without the key a stub agent is used. Tracing goes to Langfuse Cloud (project keys in `.env`); for a local Langfuse run `make up-langfuse`.

| Service | Default address |
|---|---|
| Frontend | http://localhost:3000 |
| API (Swagger) | http://localhost:8000/docs |
| Langfuse | https://cloud.langfuse.com (or http://localhost:3001 after `make up-langfuse`) |
| Application PostgreSQL | `localhost:5442` |
| Demo database | `localhost:5443` |
| Qdrant | http://localhost:6333/dashboard |

If a port is taken, override it in `.env` (`FRONTEND_PORT`, `BACKEND_PORT`, `APP_DB_PORT`, `TARGET_DB_PORT`).

All environment variables are listed in [`.env.example`](.env.example). The LLM keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) and the Langfuse Cloud keys are entered by hand; the other secrets are generated.

**Development without Docker and checks:**

```bash
make seed      # fill the demo database (~8 s; SCALE=0.1 for a smaller volume)
make smoke     # 10 questions to the agent with a real LLM
make index     # reindex the source schemas in Qdrant
make prompts   # upload the prompts to Langfuse (MSG="what changed")
make migrate   # application database migrations (also applied when the backend starts)
make lint      # ruff + mypy (strict) + eslint + tsc + prettier
make test      # pytest (backend, demo database) + Vitest and the frontend build
make test-e2e  # Playwright against the running stack (needs AGENT_MODE=fake in .env)
make format    # automatic formatting
cd backend && uv run uvicorn app.main:app --reload
cd frontend && npm run dev   # BACKEND_URL=http://localhost:8000 by default
```

Pre-commit hooks (ruff, prettier, gitleaks) are installed with `uv tool install pre-commit && pre-commit install`.

**Running the evaluation** (method and results are in [EVALS.md](EVALS.md)):

```bash
make eval-data                                   # Spider and BIRD → PostgreSQL
make eval SUITE=spider_subset CONFIG=agent LIMIT=100
make eval SUITE=spider_subset CONFIG=baseline LIMIT=100
make eval-smoke                                  # 50 questions with regression thresholds
```

## 15. LLM engineering techniques used

The table maps techniques from the course knowledge base (nFactorial "AI Engineer") to their use in the project:

| Technique | Source | Where it is used |
|---|---|---|
| LangGraph `StateGraph`, `route_fn`, reducers | AI Engineering, LangGraph section | Agent graph, routing in code, `add_messages` for history |
| Self-reflection with a code critic | AI Engineering, Self-Reflection | SQL validator as a deterministic critic, self-correction loop with a limit |
| Human-in-the-loop + checkpointer | AI Engineering, HITL | `interrupt()` for ambiguity clarification, `AsyncPostgresSaver`, resume by `thread_id` |
| Just-in-time context | Prompting / Context Engineering | Only the linked part of the schema and 2–3 sample values go into the prompt, not the whole database |
| Text-to-SQL pipeline + query routing | Prompting / Memory / Tools; RAG | Structured data is handled through SQL, not through vector search |
| Hybrid search (dense + BM25) + RRF | RAG | Schema linking by column names (exact matches) and descriptions (meaning) |
| Multilingual embeddings chosen on an own golden set | RAG, embeddings | Questions in Russian with a schema in English (ADR-015) |
| Dynamic few-shot | Prompting | Similar "question → SQL" pairs from Qdrant |
| Structured output (Pydantic) | AI Security, Prompting | Ambiguity verdict, routes, chart specification |
| Multi-level defence (5 levels) | AI Security | Input guardrail, `<untrusted_data>`, least privilege, execution control |
| Model per node, temperature | AI Engineering, model choice | A strong model for SQL generation (`temperature` ≈ 0), a cheaper one for classification and explanation |
| Tracing, evals, prompt management | AI Engineering, LLMOps | Langfuse Cloud, prompts in Prompt Management, golden sets, A/B with McNemar's test, smoke eval in CI |
| Fallback between models | Requirements of the course final project | Switch to the fallback provider (Anthropic) when the main one fails |

**Optional extensions.** They cover the remaining requirements of the course final project and are not part of the required diploma scope:

- **Own MCP server** (FastMCP) with the tools `list_tables`, `describe_table`, `validate_sql`, `explain_query`, `run_readonly_query`. Through it, the validator and the introspection can be used from Claude Desktop or Cursor.
- **Skill** (`skills/suhbat2db/SKILL.md`) with rules for this MCP server: "first `describe_table`, then `validate_sql`, never execute without validation".
- **Parsing of database documentation** (a data dictionary in PDF/DOCX via Docling) to enrich column descriptions in `schema_elements`.
- **Semantic cache** for repeated questions (taking data freshness into account).

## 16. Work plan

The detailed plan with risks and dependencies is in [docs/roadmap.md](docs/roadmap.md).

| Period | Stage | Milestone | Status |
|---|---|---|---|
| October 2026 | Analysis and design; environment, demo database, backend, validator, agent, interface (roles 1–6); stage 1 evaluation; pre-defence documents | **Pre-defence 1, 24.10.2026**, tag `pre-defense-1` | Done |
| 25.10 – 08.11.2026 | Comments from the pre-defence, 3–5 user interviews, requirements v2 | Interview notes | Planned |
| November 2026 | Prompt v2 based on the error analysis; draft of chapter 1 | `EVALS.md` v2 | Planned |
| December 2026 | Stage 2 evaluation: full samples, second seed, experiments 3–5, κ, error analysis | Full `EVALS.md` | Planned |
| January 2027 | Chapter 2 | **Pre-defence 2**, tag `pre-defense-2` | Planned |
| February – March 2027 | Chapters 3–4, conference abstract, optional MCP server | Draft text | Planned |
| April 2027 | User testing, full text, plagiarism check | Plagiarism check certificate | Planned |
| May 2027 | Presentation, demo, backup video | **Final pre-defence**, tag `final-pre-defense`; defence | Planned |

## 17. Limitations and open questions

- Only one dialect is supported (**PostgreSQL**). Other DBMSs are possible through sqlglot dialects but are outside the scope.
- Execution accuracy can count a wrong query as correct if the result matches by chance. For this reason the errors on the own dataset are analysed by hand.
- The set of ambiguous questions was created by the author and is limited in size. Conclusions about ambiguity detection apply only to the covered types.
- In the experiments a **simulated user** answers the clarifying questions from the labels. The behaviour of real users is checked separately during user testing.
- On strict EX on Spider and BIRD the agent is still behind the baseline: it adds explanatory columns and sometimes refuses by mistake. The detector does not recognise the "schema" type of ambiguity. Fixes and their check on held-out questions are planned for stage 2 of the evaluation ([EVALS.md](EVALS.md#what-the-metrics-do-not-show)).
- The LLM and embedding models, their versions and prices are recorded in the run reports (`evals/reports/`).

## 18. Literature and benchmarks

The full review with an analysis table is in [docs/literature_review.md](docs/literature_review.md). The main works:

- Yu T. et al. *Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task.* EMNLP 2018.
- Li J. et al. *Can LLM Already Serve as A Database Interface? A BIg Bench for Large-Scale Database Grounded Text-to-SQLs (BIRD).* NeurIPS 2023.
- Pourreza M., Rafiei D. *DIN-SQL: Decomposed In-Context Learning of Text-to-SQL with Self-Correction.* NeurIPS 2023.
- Gao D. et al. *Text-to-SQL Empowered by Large Language Models: A Benchmark Evaluation (DAIL-SQL).* VLDB 2024.
- Documentation: [LangGraph](https://langchain-ai.github.io/langgraph/), [sqlglot](https://sqlglot.com/), [Qdrant](https://qdrant.tech/documentation/), [Langfuse](https://langfuse.com/docs), [FastAPI](https://fastapi.tiangolo.com/).

## 19. Use of AI tools

The code, tests and documentation of this repository were written with the AI coding assistant Claude Code (Anthropic) under the author's direction. The author set the topic, the architecture, the requirements and the design of the experiments, and reviewed and ran every change. Correctness is checked independently of the assistant: by the unit, integration and e2e tests in CI, the SQL validator test set and the reproducible evaluation (`EVALS.md`).

The core of the system (roles 1–6) was added on 19.10.2026 in a few large commits that follow the plan in [docs/roles](docs/roles/README.md). Since 22.10.2026 every change goes through a YouTrack task, a branch and a pull request. The decision was recorded after the supervisor's comment of 24.10.2026 ([docs/supervisor_feedback.md](docs/supervisor_feedback.md)).

---

<sub>Diploma project, School of Software Engineering, 2026–2027.</sub>
