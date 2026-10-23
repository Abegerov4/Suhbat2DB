# Submission: probationary period 1 (pre-defence 1)

| | |
|---|---|
| Project | Suhbat2DB: a web platform for conversational analysis of relational data using an AI agent with ambiguous query clarification and SQL query validation |
| Student | Aldiyar Zhangabyl, group SE-2425 (individual project) |
| Supervisor | A. A. Sakhipov, PhD, Assistant Professor, School of Software Engineering |
| Repository | [github.com/Abegerov4/Suhbat2DB](https://github.com/Abegerov4/Suhbat2DB) (public) |
| Submitted version | Tag [`prob-period-1`](https://github.com/Abegerov4/Suhbat2DB/tree/prob-period-1) (the same commit as `pre-defense-1`) |
| YouTrack | [wasm.youtrack.cloud/issues/DIP](https://wasm.youtrack.cloud/issues/DIP) |
| Prototype | [Figma, clickable flow](https://www.figma.com/proto/M1KIz4KLirQv3UrLMaCJO4?node-id=1-3&starting-point-node-id=1%3A3); working application started with `make up` |
| Diagram sources | [docs/diagrams](https://github.com/Abegerov4/Suhbat2DB/tree/prob-period-1/docs/diagrams) (Mermaid `*.mmd`, SVG exports next to them) |

## Completed work

- Analysis: proposal and scope, evidence of relevance from the available data, literature review (24 scientific publications, 20 of them from 2023–2026), comparison of 5 systems and 2 research prototypes on 9 criteria, comparison of technologies for 7 decisions.
- Requirements: 17 functional and 16 non-functional requirements with priorities, acceptance criteria and a traceability table.
- Architecture: description of the components, 24 architectural decisions (ADR), context, use case, component, deployment, agent graph and sequence diagrams.
- Working version: FastAPI backend, LangGraph agent with clarification of ambiguous questions, five-level SQL validator, schema linking over Qdrant, Next.js interface, Docker Compose, CI with tests.
- Prototype: Figma prototype of 13 screens with the main scenarios.
- Evaluation, stage 1: clarification raises accuracy on ambiguous questions from 40.3% to 67.7% (p < 0.001); 100% of 134 attacks are blocked.
- Project management: YouTrack tasks, branches and pull requests linked to tasks, roadmap with risks and dependencies.

## Known limitations

- Interviews with potential users have not been held yet; the needs of the target users are assumptions ([section 2](../relevance.md)).
- On strict EX the agent is below the baseline on Spider (63% vs 72%); the main causes are extra explanatory columns and false refusals.
- The detector does not recognise the "schema" type of ambiguity (0 of 6); 11.4% of clear questions get an unnecessary clarification.
- One of 6 indirect injections changed the text of the answer (the data was not affected).
- In the experiments the clarifying questions are answered by a simulated user; the `ambiguous_ru` labels were checked by one person.
- Only PostgreSQL is supported.

## Outstanding tasks

- 3–5 user interviews and requirements v2 (25.10 – 08.11.2026).
- Recording the supervisor's and committee's comments and the fixes made for them.
- Prompt v2: fewer false refusals and unnecessary clarifications, the "schema" ambiguity, protection of the explanation against injection (November 2026).
- Stage 2 evaluation: full samples, a second seed, experiments 3–5, a second annotator (December 2026).
- Diploma text, chapters 1–4; pre-defence 2 (January 2027) and the final pre-defence (May 2027).
