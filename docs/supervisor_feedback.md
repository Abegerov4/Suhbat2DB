# Supervisor feedback

> Status on 24.10.2026. Meeting notes are kept in `docs/meetings/YYYY-MM-DD.md` by the [template](templates/supervisor_meeting.md). Each comment that requires action becomes a YouTrack task, and the table below links it to the commit or pull request that addresses it.

## 1. Reviews so far

| Date | What was reviewed | Feedback | Decision and result |
|---|---|---|---|
| 07–18.10.2026 | Topic and the "Justification of the feasibility of the diploma work": topic in Russian and English, objectives and stages, methods and technologies, expected result, supervision plan | Topic and justification approved | Work started on the approved topic; the stages of the justification became the [roadmap](roadmap.md) |
| 24.10.2026 | Pre-defence 1 materials (tag `prob-period-1` / `pre-defense-1`): README, proposal, requirements, ARCHITECTURE.md, EVALS.md, relevance, verification plan, roadmap, repository history | Written comments, five points (section 2). The work is assessed as ahead of schedule; points 1 and 2 matter before the pre-defence, the rest before stage 2 of the evaluation | Decisions and tasks in section 2; the quick fixes are in PR #11 |

## 2. Comments and decisions

| # | Comment | Decision | Task | Result (commit / PR) |
|---|---|---|---|---|
| 1 | Authorship and development process: the core code (roles 1–6) was added on 19.10.2026 in nine commits within about 4.5 hours; the use of AI assistants is not disclosed | Accepted. Section 19 "Use of AI tools" added to the README: which tool, for which parts, how the output is checked. The same section will go into the thesis. One module will be explained without preparation at the next meeting. Small commits through DIP tasks continue, as since 22.10.2026 | [DIP-43](https://wasm.youtrack.cloud/issue/DIP-43) | [PR #11](https://github.com/Abegerov4/Suhbat2DB/pull/11) |
| 2 | Experiment 1: the must requirement FR-11 is not met (Spider 63% vs 72%); relaxed EX and several thresholds were introduced after stage 1, which makes it easy to fit the metric to the result | Accepted. Before stage 2 the protocol is fixed in writing: strict EX as the primary metric, the hypotheses, the thresholds and a held-out question set not used in error analysis. FR-11 will be reformulated as "not worse than the baseline within N pp, plus gains in clarification and safety", with a justification, and the change recorded here. The negative stage 1 result will be described in chapter 4 | [DIP-44](https://wasm.youtrack.cloud/issue/DIP-44) | Planned, due 15.11.2026 |
| 3 | Validity of experiment 2: the dataset, labels, demo database and examples are all made by the author; the user is simulated by an LLM; labels checked by one person | Accepted. Second annotator and Cohen's κ moved to November; clarification will be tested on part of AMBROSIA or AmbiQT and in a pilot with 5–8 real people in November–December; user testing moved before chapter 4 | [DIP-27](https://wasm.youtrack.cloud/issue/DIP-27), [DIP-45](https://wasm.youtrack.cloud/issue/DIP-45) | Roadmap updated in [PR #11](https://github.com/Abegerov4/Suhbat2DB/pull/11); experiments planned |
| 4 | Users and relevance: four groups, all needs are assumptions; no real database for the demonstration; Kazakh is outside the optimisation scope | Accepted. Primary group: teachers and students of the AITU database course, at least 5 interviews; confirmation criteria for statements 5–8 written down before the interviews. Demonstration on open data from data.egov.kz. Kazakh is in scope: questions in Kazakh must not be refused (FR-16 raised to Should), without separate optimisation | [DIP-19](https://wasm.youtrack.cloud/issue/DIP-19), [DIP-46](https://wasm.youtrack.cloud/issue/DIP-46), [DIP-21](https://wasm.youtrack.cloud/issue/DIP-21) | [proposal](proposal.md#2-target-users), [relevance](relevance.md#5-confirmation-criteria) updated in [PR #11](https://github.com/Abegerov4/Suhbat2DB/pull/11); interviews planned |
| 5 | Security and data flow: attacks written by the author, only 6 indirect injections; what leaves the user's database is not collected in one place | Accepted. Data-flow table "step → what is sent → where" with a conclusion on which data the system may be used with: [data_flow.md](data_flow.md). External attack set (sources 13–14) and at least 30 indirect injections; a local model as a "could" option | [DIP-43](https://wasm.youtrack.cloud/issue/DIP-43), [DIP-47](https://wasm.youtrack.cloud/issue/DIP-47) | Data flow in [PR #11](https://github.com/Abegerov4/Suhbat2DB/pull/11); attack set planned |

## 3. Review of changes in the repository

The project is individual, so the supervisor reviews selected significant pull requests at agreed checkpoints (Git step 7). Planned checkpoints:

- after pre-defence 1: the fixes made in response to the committee's and supervisor's comments;
- November 2026: the evaluation protocol (DIP-44) and prompt v2 (false refusals, unnecessary clarifications, "schema" ambiguity);
- December 2026: stage 2 evaluation results.
