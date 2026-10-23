# Project proposal

| | |
|---|---|
| Topic | Development of a Web Platform for Conversational Analysis of Relational Data Using an AI Agent with Ambiguous Query Clarification and SQL Query Validation |
| Topic (Russian) | Разработка веб-платформы диалогового анализа реляционных данных на основе ИИ-агента с уточнением неоднозначных запросов и проверкой SQL-запросов |
| Working title | Suhbat2DB (from the Kazakh *сұхбат*, "conversation, dialogue") |
| Author | Aldiyar Zhangabyl, group SE-2425, Software Engineering programme. The project is individual, and the author carries out all stages |
| Supervisor | A. A. Sakhipov, PhD, Assistant Professor, School of Software Engineering |
| Timeline | October 2026 – May 2027 ([roadmap](roadmap.md)) |

## 1. Problem

Analysts, managers, teachers and students who do not know SQL need quick access to data in relational databases. Today they either wait until a specialist writes the query or ask an LLM directly: "write SQL for…". The second way has three weak points.

1. The query looks plausible but is wrong. The model refers to columns that do not exist or joins tables on the wrong keys. The query runs, the answer is wrong, and the user does not notice.
2. The question is ambiguous. In "sales for last quarter" it is unclear what to count (revenue or number of orders) and which quarter is meant (calendar or fiscal). The model silently picks one reading, and the user gets an answer to a different question.
3. The query is dangerous. Because of the wording of the question, prompt injection or instructions hidden in the data itself, the model can generate `DROP`, `DELETE`, a heavy Cartesian `JOIN` or a call to DBMS system functions.

Public Text-to-SQL benchmarks (Spider, BIRD) hardly test the second and third points: each question has one reference answer, and the safety of execution is not evaluated ([literature review](literature_review.md)).

## 2. Target users

| Group | Task | What matters to them |
|---|---|---|
| Analysts and business staff | Get answers from data without waiting for an SQL specialist | A correct answer and a way to check how it was obtained |
| Managers | Look at figures and compare periods | That everyone understands "revenue" and "quarter" in the same way |
| Teachers and students of database courses | Study how a question turns into SQL | Visible SQL, explanation of errors and corrections |
| Data administrators | Connect databases to the system | A guarantee that the system will not change the data or overload the DBMS |

Interviews with users that should confirm these needs are still to be done ([template](templates/interview.md), dates in the [roadmap](roadmap.md)).

## 3. Aim and objectives

Aim: to develop a web platform where an AI agent answers natural-language questions about a relational database, asks back when a question is ambiguous and checks every SQL query before execution, and then to compare these mechanisms experimentally with a baseline approach.

Objectives:

1. Analyse LLM-based approaches to Text-to-SQL, agent architectures, and work on question ambiguity and on the security of LLM applications.
2. Design the platform architecture and the agent graph.
3. Implement selection of the relevant part of the schema (schema linking) using a vector index of the schema and values.
4. Implement ambiguity detection and a clarification dialogue with options tied to the schema.
5. Implement multi-level SQL validation (syntax, read-only policy, schema check, execution plan, isolated execution with limits) and a self-correction loop.
6. Implement the web interface: dialogue, SQL with a validation report, table, chart, explanation.
7. Prepare datasets and run experiments: agent vs baseline, agent with and without clarification, a check against attacks.

## 4. Expected results

- A web platform with clarification and SQL validation modules that is deployed with one command.
- Datasets: subsets of Spider and BIRD, an own set of ambiguous questions in Russian `ambiguous_ru`, and an attack set `unsafe`.
- An experimental evaluation with confidence intervals and significance tests: execution accuracy, quality of ambiguity detection, shares of blocked attacks and false blocks, cost and latency ([EVALS.md](../EVALS.md)).
- The diploma text and, as planned with the supervisor, an abstract for a student research conference.

The novelty of the work is that explicit ambiguity detection with a clarification dialogue is combined with multi-level deterministic SQL validation, and the contribution of each mechanism is measured separately.

## 5. Scope

| Included | Not included |
|---|---|
| PostgreSQL as the analysed DBMS | Other DBMSs (they can be added through sqlglot dialects, but they are outside this work) |
| Read-only access to data | Data modification, ETL, building data marts |
| Questions in Russian; English and Kazakh without separate optimisation | Voice input |
| Web interface, `admin` and `analyst` roles | Mobile application, SSO, multi-tenancy |
| LLMs through an API (OpenAI, Anthropic as the fallback provider) | Fine-tuning an own model |
| Demo database and the Spider and BIRD benchmarks | Work with real personal data |
| Tracing in Langfuse | Production operation, SLA |

If time allows: an MCP server with the validator tools and a semantic cache.

## 6. Engineering complexity

The work has to link the words of a question to the schema and values, find join paths over foreign keys and take the PostgreSQL dialect into account. The agent graph contains a self-correction loop and a pause for a human answer that survives a server restart. The system executes SQL that the model generated from untrusted input, so the protection is built as several lines of defence. A correct evaluation requires comparing SQL results, simulating the user, applying paired statistical tests and making sure that test questions do not get into the examples given to the model.

## 7. Risks

Risks and the measures against them are described in the [roadmap](roadmap.md#4-risks).

## 8. Related documents

[Requirements](requirements.md) · [Literature review](literature_review.md) · [Comparison of existing systems](existing_systems.md) · [Technology comparison](technology_comparison.md) · [Architecture](../ARCHITECTURE.md) · [Diagrams](diagrams/) · [Evaluation plan and results](../EVALS.md) · [Roadmap](roadmap.md)
