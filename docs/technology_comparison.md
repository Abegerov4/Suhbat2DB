# Technology comparison

For each main decision this document compares the alternatives; the detailed reasoning is in [ARCHITECTURE.md](../ARCHITECTURE.md#8-architectural-decisions-adr). The criteria come from the [requirements](requirements.md): clarification with a pause (FR-07), deterministic SQL validation (FR-09, NFR-01), read-only access (NFR-03), reproducibility (NFR-15) and cost (NFR-10).

Notation: "Yes" means the option fits well; "Partly" means it fits with reservations; "No" means it does not fit.

## 1. Agent orchestration

| Criterion | LangChain (LCEL chains) | CrewAI / AutoGen | Own loop on asyncio | **LangGraph** |
|---|---|---|---|---|
| Self-correction loop with a limit | No | Yes | Yes | Yes |
| Pause for a human answer that survives a restart | No | Partly, human input without persistence between HTTP requests in the standard configuration | Partly, must be written by hand | Yes, `interrupt()` + checkpoint in PostgreSQL |
| The route is chosen by code, not by the LLM | Yes | No, the agents decide | Yes | Yes, route functions |
| Streaming steps to the UI | Partly | Partly | Partly, must be written by hand | Yes |
| Tracing out of the box | Yes | Partly | No | Yes |

LangGraph was chosen: it is the only option where the clarification pause and resuming after a restart work without own code. [ADR-020](../ARCHITECTURE.md#adr-020-agent-orchestration-langgraph-instead-of-crewai-autogen-or-an-own-loop)

## 2. SQL validation

| Criterion | Regular expressions | LLM critic (a second model) | DBMS privileges only | **AST (sqlglot) + EXPLAIN + DBMS privileges** |
|---|---|---|---|---|
| Robustness to disguise (`DeLeTe`, quotes, a CTE with `DELETE`) | No | Partly, probabilistic | Yes | Yes |
| Schema check and a hint for correction | No | Partly, no guarantees | No, only the DBMS error | Yes, similar columns and tables |
| Determinism, reproducibility | Yes | No | Yes | Yes |
| Protection against heavy queries before execution | No | Partly | Partly, only a timeout | Yes, plan estimate |
| Cost and latency | Yes | No, +1 LLM call | Yes | Yes, < 3 ms without the database |

AST checks together with plan analysis and DBMS privileges were chosen. On a set of 88 attacks all were blocked, and none of 42 harmless queries was blocked. [ADR-011](../ARCHITECTURE.md#adr-011-sql-checks-on-the-ast-sqlglot-not-with-regular-expressions), [ADR-008](../ARCHITECTURE.md#adr-008-read-only-check-by-role-privileges-not-by-a-test-write), [validator.md](validator.md)

## 3. Vector index storage

| Criterion | pgvector in the application database | Chroma / FAISS in process | **Qdrant** |
|---|---|---|---|
| Hybrid search (meaning + exact names) | Partly, dense is available, the lexical part would have to be built on `tsvector` | Partly, dense only | Yes, dense + sparse with IDF, RRF in one query |
| Filter by data source | Yes | Partly | Yes, payload index |
| Index separated from service data | No | Partly | Yes |
| Number of services | Yes, no new one | Yes, no new one | Partly, +1 container |

Qdrant was chosen. At a small volume pgvector would have worked just as well; the decision came from the built-in sparse search and from keeping the index separate from the service data. [ADR-021](../ARCHITECTURE.md#adr-021-vector-index-qdrant-instead-of-pgvector), [ADR-015](../ARCHITECTURE.md#adr-015-schema-linking-text-embedding-3-large-hybrid-search-all-shortest-join-paths)

## 4. Communication between components

| Criterion | WebSocket | Polling | **REST + SSE through a BFF** |
|---|---|---|---|
| Stream of agent steps and answer tokens | Yes | No, delay | Yes |
| Compatibility with HTTP proxies and cookie authorisation | Partly, separate protocol | Yes | Yes, plain HTTP |
| Two-way channel | Yes, (not needed: the clarification answer comes in a separate request) | — | Partly, server → client only |
| Complexity | Partly, connection state | Yes | Yes |

REST and SSE were chosen. The browser talks only to Next.js, which keeps the JWT in an httpOnly cookie. [ADR-017](../ARCHITECTURE.md#adr-017-backend-for-frontend-and-jwt-in-an-httponly-cookie), [ADR-010](../ARCHITECTURE.md#adr-010-the-sse-response-is-built-by-hand), [ADR-019](../ARCHITECTURE.md#adr-019-the-agent-turn-does-not-depend-on-the-connection)

## 5. LLM models

| Criterion | One strong model for all nodes | Reasoning model (o-series, gpt-5) | Local open model | **gpt-4.1 for precise nodes + gpt-4.1-mini for the rest** |
|---|---|---|---|---|
| Quality of SQL generation | Yes | Yes | Partly, lower on complex queries | Yes |
| `temperature` for experiments | Yes | No, not accepted | Yes | Yes |
| Cost per question | Partly | No, higher | Yes, no API fees, but a GPU is needed | Yes, $0.008–0.012 |
| Latency | Yes | No, higher | Partly, depends on hardware | Yes, median 4–5 s |

The model is chosen separately for each node, with Anthropic as the fallback provider. A comparison with another model is planned in experiment 5. [ADR-014](../ARCHITECTURE.md#adr-014-llm-models-gpt-41-for-precise-nodes-gpt-41-mini-for-the-rest)

## 6. Tracing and observability

| Criterion | LangSmith | Phoenix (Arize) | **Langfuse** |
|---|---|---|---|
| LangGraph integration | Yes, native | Partly, through OpenTelemetry | Yes, callback |
| Self-hosting | Partly, enterprise version only | Yes | Yes. MIT, docker compose |
| Prompt versions linked to generations | Yes | Partly | Yes |
| User ratings on traces | Yes | Yes | Yes |

Langfuse was chosen, in the cloud version by default. [ADR-022](../ARCHITECTURE.md#adr-022-tracing-langfuse-instead-of-langsmith), [ADR-013](../ARCHITECTURE.md#adr-013-langfuse-cloud-by-default-local-langfuse-optional)

## 7. Backend and frontend platform

| Decision | Alternatives | Choice and reason |
|---|---|---|
| Backend | Django + DRF; Node.js (NestJS) | **FastAPI**: asynchronous code for the LLM and SSE, Pydantic schemas shared with the agent's structured output, the Python ecosystem for LLMs and sqlglot |
| Frontend | SPA on Vite + React; Streamlit | **Next.js 16**: server routes as a BFF (the token does not reach the browser), the React ecosystem (shadcn/ui, Recharts). Streamlit is simpler but gives no control over session security or the chat interface |
| DBMS | MySQL; SQLite | **PostgreSQL 17**: roles and read-only transactions, `EXPLAIN (FORMAT JSON)`, storage of LangGraph checkpoints; Spider and BIRD were moved from SQLite with a check of the results |
