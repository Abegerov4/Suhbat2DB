# Verification and evaluation plan

> This document connects the testing of the implementation with the experiments that show whether the project aim is reached. The method, the datasets and the stage 1 results are described in [EVALS.md](../EVALS.md); every requirement has its verification method in the [requirements](requirements.md#4-traceability-objectives--requirements--verification).

## 1. Testing of the implementation

| Level | What is checked | Tools | When it runs |
|---|---|---|---|
| Unit and integration tests, backend | API, authentication and roles, data sources, sessions, the agent turn lifecycle, migrations | pytest against a real PostgreSQL (`make test`) | CI on every push (`backend.yml`) |
| SQL validator | Each of the 5 levels; 88 SQL attacks and 42 harmless queries | pytest, `tests/validator` | CI on every push |
| Demo database | Schema, seed data and the deliberate "traps" | pytest (`demo_db.yml`) | CI on every push |
| Frontend | Components and the production build | Vitest, `tsc`, eslint | CI on every push (`frontend.yml`) |
| End-to-end | Login, dialogue with clarification, phone layout, accessibility (axe) | Playwright against the running stack with a stub agent (`make test-e2e`) | CI on push to `main` (`e2e.yml`) |
| Regression of answer quality | 50 questions with fixed thresholds | `make eval-smoke` with a real LLM | CI on pull requests that change the agent, the validator or the datasets (`evals.yml`) |

## 2. How the project aim is demonstrated

| Objective | Metric | Baseline for comparison | Measurement conditions | Target |
|---|---|---|---|---|
| Answer questions correctly | Execution Accuracy (strict and relaxed) on Spider and BIRD subsets | One call to the same model with the full schema, without clarification, schema check or self-correction | gpt-4.1, temperature 0, fixed date and prompts, cached LLM responses, bootstrap 95% CI, McNemar test | Higher than the baseline (FR-11); not reached in stage 1 on strict EX |
| Clarify ambiguous questions | EX on ambiguous questions with and without clarification; detection precision, recall, F1; share of unnecessary clarifications | The same agent with clarification switched off | `ambiguous_ru`, simulated user (LLM judge) | Significant EX gain (FR-08) |
| Block dangerous queries | Share of blocked attacks; share of false blocks | — | `unsafe` set: natural-language and SQL attacks, indirect injections | 100% blocked, ≤ 5% false blocks (NFR-01, NFR-02) |
| Keep the system usable | Median latency and cost per question | The baseline | The same runs | NFR-08, NFR-10 |

## 3. Stages

- **Stage 1 (October 2026, done):** subsets of Spider (100) and BIRD (60), full `ambiguous_ru` and `unsafe`, one seed. Results are in [EVALS.md](../EVALS.md).
- **Stage 2 (December 2026):** full subsets of Spider (200) and BIRD (150), a second seed, experiments 3–5, error classification. Labelling by a second annotator (Cohen's κ) is done earlier, in November (DIP-27).
- **External check of clarification and pilot (November–December 2026):** part of AMBROSIA or AmbiQT and 5–8 real people answering the clarifying questions (DIP-45); the evaluation protocol is fixed in writing before stage 2 (DIP-44).
- **User testing (March 2027, before chapter 4):** real users solve tasks with the system; the scenarios are chosen based on the interviews ([evidence of relevance](relevance.md)).
