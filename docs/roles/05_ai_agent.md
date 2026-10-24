# Role 5. AI Agent (LLM Engineer)

**Status: completed** (October 2026). Graph: [docs/graph.md](../graph.md); state: [CONTRACTS §5](../CONTRACTS.md#5-agent-state-langgraph).

**Aim:** a LangGraph agent that replaces `FakeAgentRunner`. The agent links the question to the schema, clarifies ambiguities, generates SQL, corrects it using the validator report, executes it and explains the result. Every step is traced.
**Depends on:** roles 3 (the `AgentRunner` interface, `SchemaSnapshot`) and 4 (the validator).
**Needed for:** Frontend (real events), Evals (the `agent` and `baseline` configurations).

## Structure

```text
backend/app/agent/
├── llm.py              # LLM interface, model per node, structured output, fallback provider
├── prompts/*.md        # v1 prompts (guard, ambiguity, generate_sql, explain, baseline) + registry
├── retrieval/
│   ├── sparse.py       # BM25 tokenisation: RU/EN stemming, identifier splitting
│   ├── embeddings.py   # OpenAI embeddings; hash embeddings for tests
│   ├── store.py        # Qdrant: schema and examples, dense + BM25, RRF
│   └── linker.py       # table selection and completion of JOIN paths over foreign keys
├── examples/demo.json  # 20 verified "question → SQL" pairs for few-shot
├── state.py            # AgentState, AgentContext
├── nodes.py            # the 10 graph nodes
├── graph.py            # StateGraph, routing in code
├── charts.py           # chart choice by column types
├── langgraph_runner.py # graph stream → SSE + Langfuse
├── baseline.py         # baseline approach for experiment 1
└── factory.py          # assembly at application startup
```

## Tasks

### 5.1 LLM layer
- [x] The `LLM` interface (`structured`, `stream_text`) and an implementation on LangChain (OpenAI, Anthropic). Tests use a scripted `FakeLLM`
- [x] Model per node: `strong` = **gpt-4.1** (`detect_ambiguity`, `generate_sql`, temperature 0), `fast` = **gpt-4.1-mini** (`guard_input`, `explain`, temperature 0 and 0.3). The models are set in env
- [x] Reasoning models (gpt-5*, the o-series) do not accept `temperature`, so the parameter is not passed (`supports_temperature`)
- [x] Fallback provider through `with_fallbacks` if its key is set. Currently only an OpenAI key is available
- [x] Langfuse: a `CallbackHandler` with a `trace_id` created in advance, the session and user in the metadata; the `trace_id` goes to the SSE `done` event and to the message. like/dislike is sent to Langfuse as the `user_feedback` score
- [ ] ~~`LLM_MAX_COST_PER_REQUEST`~~ not needed: the cost is bounded by the limits on attempts and clarifications, and the actual cost is ≈ $0.01 per question (Langfuse)

### 5.2 Retrieval: schema linking
- [x] Three kinds of documents: table, column (type, FK, comment), value of a categorical column. The Qdrant collections are named after the embedding model
- [x] Hybrid dense + BM25 search (Qdrant `Modifier.IDF`, tokenisation with stemming) fused with RRF. The `dense` and `sparse` modes are kept for experiments
- [x] Tables are ranked by the sum of the reciprocal ranks of their documents; a value match weighs 1.5 times more
- [x] Completion of JOIN paths: each selected table is connected to the main table **along all shortest paths** of the FK graph. The first version took one path and chose it arbitrarily, while "orders in Almaty region" has two valid paths: through the customer and through the manager
- [x] Value linking: the values found are listed first in `[values: …]`
- [x] The set [`evals/datasets/schema_linking/demo.jsonl`](../../evals/datasets/schema_linking/demo.jsonl) has 40 questions with reference tables; the script is `scripts/eval_schema_linking.py`

**Results** (share of questions for which all required tables were found, top-5):

| Embeddings | dense | BM25 | hybrid |
|---|---|---|---|
| text-embedding-3-small | 0.900 | 0.800 | 0.900 |
| text-embedding-3-large | **0.975** | — | **0.975** |

Chosen: **text-embedding-3-large, hybrid, 5 tables**, with recall 0.975 against the requirement of ≥ 0.95. BM25 alone is weak because the questions are in Russian and the identifiers are in English. The hybrid mode was kept although the metrics are equal: it covers exact matches of codes and names in real databases. The only miss is a question with two valid join paths. Tuning on the same 40 questions was stopped so as not to fit the result to the set.

### 5.3 Baseline
- [x] `BaselineRunner`: full schema + question → SQL in one call → only validator levels 2 and 5

### 5.4 Graph
- [x] 10 nodes; the route is chosen only by the Python function `route()` from the `state["route"]` field
- [x] Limits: 3 generation attempts, 2 rounds of clarification
- [x] `AsyncPostgresSaver` on the application database, `thread_id = session_id`
- [x] `LangGraphAgentRunner`: `astream(stream_mode=["custom", "updates"])` → CONTRACTS §2 events; `__interrupt__` → `clarification`
- [x] Diagram from the code: [docs/graph.md](../graph.md)

### 5.5 Generation and self-correction
- [x] Prompt v1: rules (SELECT only, FKs, values from the lists, dates through `date_trunc`, defaults, aliases), schema, few-shot, dialogue context, errors of earlier attempts
- [x] Prompts in Langfuse Prompt Management (`suhbat2db-*`, v1, label production) via `make prompts`. With `PROMPTS_FROM_LANGFUSE=true` they are taken from there, otherwise from the files
- [x] Self-correction: the SQL of the previous attempt, the level, the message and the validator hint are passed to the generator. A fatal policy violation leads to a refusal without a retry

### 5.6 Ambiguity and clarification
- [x] `AmbiguityVerdict`: options with an `interpretation` tied to schema columns; at most 2 ambiguities and 2–4 options
- [x] The prompt lists the defaults that need no clarification and examples of clear questions (against over-clarification)
- [x] `interrupt()` → `Command(resume=…)`; a free-text answer is accepted as well
- [x] Session memory: earlier clarifications are passed to the detector in later turns

### 5.7 Guard and explanation
- [x] `guard_input`: allow / modify / injection / off_topic; doubtful cases are resolved as allow, because the validator blocks writes anyway
- [x] The schema, values and result are passed inside `<schema>` and `<query_result>` boundaries with a statement that this is data, not instructions
- [x] Code chooses the chart type (date → line, ≤ 6 positive categories → pie, otherwise bar, more than 30 categories → no chart)
- [x] The explanation is streamed token by token. Numbers in the explanation that are not in the result are logged as a warning

### 5.8 Tests
- [x] 38 agent tests: schema search (in-memory Qdrant), charts, the whole graph (normal answer, self-correction with a hint, execution error, attempts used up, fatal SQL, refusals, clarification and resume, session memory, round limit), baseline, the runner through the API, the LLM client, the prompt registry
- [x] Smoke test with a real LLM: `make smoke` (10 questions)

## Smoke test (gpt-4.1, demo database)

The questions were asked in Russian; English translations are given.

| Question | Behaviour |
|---|---|
| How many orders are there in total? | Correct SQL, 100,000 |
| Top 5 regions by revenue for 2025 | Correct JOIN through the customer, pie |
| Show sales for last quarter | 2 clarifications (measure, type of quarter) → revenue, calendar → 5.61 billion ₸ (matches docs/demo_db.md) |
| Which payment method is the most popular? | kaspi_qr |
| Monthly revenue trend in 2026 | line, 10 months |
| Average order value online and offline | **Unnecessary clarification**: the question is clear (over-clarification, measured in role 7) |
| Who is the best manager? | Clarification of the criterion → by revenue |
| How many customers have never bought anything? | 7,100 (interpretation "without cancelled orders") |
| Delete all cancelled orders | Refusal at `guard_input` |
| Write a poem about autumn | Refusal `out_of_scope` |

A turn costs about **$0.01** (2 gpt-4.1 calls of ~2.4 thousand tokens + gpt-4.1-mini), and the latency is 4–8 s.

## Definition of Done
- [x] `FakeAgentRunner` is replaced (when an LLM key is set), and the events match CONTRACTS §2
- [x] "Show sales for last quarter" → clarification → answer works end to end
- [x] Langfuse shows the full trace: nodes, LLM calls, tokens, cost
- [x] Schema recall ≥ 0.95: **0.975**
- [x] The v1 prompts are uploaded to Langfuse

## Knowledge base
- `ai_engineering.md` §2.3, §5 (StateGraph, route_fn, reducers), §6 (self-reflection: the critic is code), §7 (HITL + checkpointer), §2.6 (model per node)
- `rag.md` §2.3–2.4 (embeddings, hybrid + RRF), §7 (retrieval metrics)
- `prompting_memory_tools.md` §2.1–2.3 (prompting, just-in-time), §5.5 (Text-to-SQL pipeline)
- `ai_security.md` §4.3–4.4 (untrusted data, input guardrail)
