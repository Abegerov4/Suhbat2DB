# Data flow: what leaves the user's database

> Added on 24.10.2026 after the supervisor's comment 5 ([supervisor feedback](supervisor_feedback.md)). The table follows the agent code (`backend/app/agent/nodes.py`, `retrieval/`, `langgraph_runner.py`) in the default configuration: OpenAI models and Langfuse Cloud.

## 1. Data sent outside the system

| Step | What is sent | Where |
|---|---|---|
| Indexing a data source (`make index`, connecting a source) | Table and column names, types, comments, up to 20 sample values of each categorical column | OpenAI embeddings API (`text-embedding-3-large`) |
| Schema linking | The user's question | OpenAI embeddings API |
| `guard_input` | The question, the dialogue context and a short summary of the schema (table names and comments) | OpenAI chat model |
| `detect_ambiguity`, `clarify` | The question, the linked part of the schema with comments and sample values, earlier clarifications | OpenAI chat model |
| `generate_sql`, `self_correct` | The same, plus SQL examples, the dialogue history and the validator error of the previous attempt | OpenAI chat model |
| `explain_and_visualize` | The question, the SQL and **the query result: column names and up to 50 rows** | OpenAI chat model |
| Tracing (every step above) | The full prompts and model answers, including the rows of the result; personal data is not masked | Langfuse Cloud (EU) |
| Fallback (only if `LLM_FALLBACK_PROVIDER` is set) | The same as for the OpenAI chat model | Anthropic API |

Nothing else leaves the system. The validator (levels 1–4) and the execution of SQL (level 5) run inside the system; the analysed database is never accessed by an external service directly, and the role `s2d_reader` can only read.

## 2. Data that stays inside

| Data | Where it is stored |
|---|---|
| Full table contents | Only in the analysed database; the system reads at most 1000 rows per query |
| Query results shown to the user | The browser and the message history in app-db |
| Connection string of a source | app-db, encrypted with Fernet |
| Schema snapshot and vectors | app-db and Qdrant (local container) |

## 3. Which data the system may be used with

- **Open, synthetic or educational data** (the demo database, Spider, BIRD, data.egov.kz): may be used in the default configuration.
- **Internal data without personal information:** may be used if the organisation accepts that the schema, sample values and up to 50 result rows are processed by OpenAI and stored in Langfuse Cloud. Tracing can be switched to a local Langfuse (`make up-langfuse`) so that traces stay inside.
- **Personal or confidential data:** must not be used in the default configuration. A local model for generation and embeddings is a "could" option ([DIP-47](https://wasm.youtrack.cloud/issue/DIP-47)); until it exists, such data is out of scope.
