# Requirements and acceptance criteria

Priorities follow MoSCoW. M (must): without it the aim of the project is not reached. S (should): important but not blocking. C (could): if time allows. Every mandatory requirement has a verifiable criterion and a way to check it. The status is given as of 21.10.2026.

Status values: "Done" means implemented and verified; "Partly" means partly done; "Not met" means not done; "Planned" means planned for a later stage.

The thresholds of FR-08, FR-11, NFR-01, NFR-03…06, NFR-09, NFR-14 and NFR-16 were set in the plan by roles ([docs/roles](roles/README.md)) before the implementation. I formulated the thresholds of NFR-02, NFR-07, NFR-08 and NFR-10 on 21.10.2026, after stage 1 of the evaluation.

## 1. Functional requirements

### Access and data sources

| ID | Requirement | Pr. | Acceptance criterion | Verification | Status |
|---|---|---|---|---|---|
| FR-01 | Analyst registration, login and logout | M | A registered user logs in with email and password; a wrong password returns 401; the session token is not accessible to JavaScript | `tests/test_auth.py`, e2e `auth.spec.ts` | Done |
| FR-02 | `admin` and `analyst` roles | M | Only `admin` can connect, reindex and delete sources; an analyst request gets 403 | `test_analyst_cannot_manage_datasources` | Done |
| FR-03 | Connection of a PostgreSQL source with read privileges only | M | A source whose role can write, create objects or read server files is not saved; the user sees the list of violations. The connection string is stored encrypted | `test_writable_role_is_rejected`, `test_connection_string_is_stored_encrypted` | Done |
| FR-04 | Schema snapshot and indexing | M | After connection the tables, columns, types, FKs, comments and values of categorical columns (≤ 20) are available; the schema is indexed in Qdrant; reindexing is possible | `test_readonly_datasource_is_indexed`, `test_schema_not_ready_reindex_delete` | Done |

### Dialogue and answer

| ID | Requirement | Pr. | Acceptance criterion | Verification | Status |
|---|---|---|---|---|---|
| FR-05 | Dialogue sessions with history | M | The user creates a session for the selected source and sees the message history; a follow-up question "and by region?" is understood in the context of the previous one | `tests/test_sessions.py`, graph tests (session memory) | Done |
| FR-06 | Answer to a natural-language question | M | The answer contains the SQL, the result table and a text explanation; the stream of agent steps is visible while the answer is produced | e2e `chat.spec.ts`, graph tests | Done |
| FR-07 | Ambiguity detection and clarification with options | M | For an ambiguous question the agent asks a clarifying question with 2–4 options tied to the schema and accepts a custom text answer; after the answer it continues from the same point; a chosen interpretation is not asked again in the session | Graph tests, e2e, experiment 2 | Done |
| FR-08 | Clarification increases accuracy on ambiguous questions | M | EX on the ambiguous questions of `ambiguous_ru` with clarification is higher than without it, with statistical significance (p < 0.05) | Experiment 2: 40.3% → 67.7%, p < 0.001 | Done |
| FR-09 | Multi-level SQL validation | M | Every SQL query passes 5 levels; for each level the user sees whether it passed and the reason for a rejection | `tests/validator`, [docs/validator.md](validator.md) | Done |
| FR-10 | Self-correction | M | After an error at levels 1, 3, 4 or in the DBMS the agent repeats generation with the reason and a hint, at most 3 attempts; an attempt to change data is rejected without correction | Graph tests (`self_correct`) | Done |
| FR-11 | The agent is more accurate than the baseline | M | Agent EX on `spider_subset` and `bird_subset` is higher than that of the baseline (same model, whole schema, one call) | Experiment 1: Spider 63% vs 72%, BIRD 38% vs 42% | Not met, stage 1 ([analysis](../EVALS.md#experiment-1-baseline-vs-agent)) |
| FR-12 | Visualisation | S | The chart type is chosen automatically from the column types; the chart, table and SQL are available in the analysis panel | `test_charts.py`, `chart.test.ts` | Done |
| FR-13 | Stopping an answer | S | The Stop button interrupts the agent and the turn is saved with a mark; closing the tab does not lose the answer | `test_turn_lifecycle.py` | Done |
| FR-14 | Like / dislike rating of an answer | S | The rating is saved and attached to the trace in Langfuse as a score | `test_sessions.py`, `test_stats.py` | Done |
| FR-15 | Overview of the query log | S | Dashboard: number of queries, share of answers with data, the level where the validator stopped SQL, clarifications, ratings | `test_stats.py` | Done |
| FR-16 | Questions in Kazakh | S | A question about data in Kazakh gets an answer, not a refusal | `unsafe`: 1 false refusal in Kazakh | Partly |
| FR-17 | MCP server with the validator tools | C | `validate_sql` and `describe_table` are available from an MCP client | — | Planned |

## 2. Non-functional requirements

| ID | Category | Requirement | Pr. | Acceptance criterion | Verification | Status |
|---|---|---|---|---|---|---|
| NFR-01 | Security | Attacks are blocked | M | 100% of the attacks in the `unsafe` set (≥ 50 in natural language) and 100% of the validator SQL attacks are blocked | Security experiment: 46/46 and 88/88 | Done |
| NFR-02 | Security | Harmless questions are not blocked | M | 0% false blocks of SQL, at most 5% of harmless natural-language questions | 0% SQL; 10% of questions (3 of 30) | Partly |
| NFR-03 | Security | Data does not change whatever the model answers | M | The connection role can only read; the query runs in a `READ ONLY` transaction; a write attempt is rejected by the DBMS | `demo_db/tests/test_reader_role.py`, executor tests | Done |
| NFR-04 | Security | Limited load on the DBMS | M | `statement_timeout` 5 s, at most 1000 rows and 2 MB of result; heavy queries are stopped | Validator tests, `unsafe` heavy: 4/4 | Done |
| NFR-05 | Security | Secrets and session | M | Secrets only in `.env`, gitleaks in pre-commit; JWT in an httpOnly cookie; argon2 passwords | `test_security.py`, e2e | Done |
| NFR-06 | Quality | Table selection | M | All required tables are found for ≥ 95% of the questions of the control set | 97.5% (40 questions); Spider 99%, BIRD 90% | Done |
| NFR-07 | Quality | Ambiguity detection | S | No target was set before the experiment. For stage 2 the proposed target is F1 ≥ 0.8 and at most 10% unnecessary clarifications | F1 0.74; unnecessary clarifications 11.4% | Planned |
| NFR-08 | Performance | Response latency | S | Median agent response ≤ 8 s, p95 ≤ 15 s (without the time spent on clarification) | 4.4–5.3 s and 8.3–12.4 s | Done |
| NFR-09 | Performance | SQL validation without the database | S | Levels 1–3 < 20 ms | Median 0.58 ms, p95 1.46 ms | Done |
| NFR-10 | Cost | Cost per question | S | ≤ $0.02 per question | $0.008–0.012 | Done |
| NFR-11 | Reliability | Turn resilience | S | A dropped connection does not lose the answer; the clarification pause survives a backend restart | `test_turn_lifecycle.py`, checkpoint in PostgreSQL | Done |
| NFR-12 | Accessibility | Interface | S | WCAG 2.1 AA by axe-core without serious or critical violations; Lighthouse Accessibility ≥ 90; works at phone width | e2e `a11y.spec.ts`, `mobile.spec.ts`; Lighthouse 96 | Done |
| NFR-13 | Observability | Tracing | S | Each turn is recorded as a trace with nodes, prompts, tokens and cost; prompts are versioned | Langfuse | Done |
| NFR-14 | Maintainability | Tests and checks | M | Linters and strict mypy without errors; coverage of `app/validator` ≥ 90%, of `api` and `services` ≥ 70%; CI on every push | CI: 96% and 93–100% | Done |
| NFR-15 | Reproducibility | Deployment and evaluation | M | `make up` starts the system on a clean machine; evaluation runs are deterministic (LLM cache, fixed date) | CI `compose.yml`; `EVALS.md` | Done |
| NFR-16 | Regression | Control of agent quality | S | Smoke eval on 50 questions in CI: EX does not drop by more than 5 pp, attack blocking 100% | `evals.yml` | Done |

## 3. Constraints

- Analysed DBMS: PostgreSQL 17; the agent connects with a read-only role.
- The LLM is called through an external API (OpenAI). Without a key the agent does not work; tests use a stub.
- The demo data is synthetic; user data is not used.

## 4. Traceability: objectives → requirements → verification

| Objective ([proposal](proposal.md#3-aim-and-objectives)) | Requirements | Where it is verified |
|---|---|---|
| 3. Schema linking | FR-04, NFR-06 | Role 5, [EVALS.md](../EVALS.md) |
| 4. Clarification | FR-07, FR-08, NFR-07 | Experiment 2 |
| 5. SQL validation and self-correction | FR-09, FR-10, NFR-01…04, NFR-09 | [docs/validator.md](validator.md), "Security" |
| 6. Web interface | FR-01…06, FR-12…15, NFR-12 | e2e tests |
| 7. Experiments | FR-08, FR-11, NFR-07, NFR-08, NFR-10 | [EVALS.md](../EVALS.md) |
