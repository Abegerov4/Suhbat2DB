# Work plan and roadmap

The project is individual: Aldiyar Zhangabyl carries out all tasks, and A. A. Sakhipov is the supervisor. According to the supervision plan, meetings with the supervisor take place once a week for about an hour, in person or online, and once a month the student shows a working version. Tasks are tracked in YouTrack, and the detailed plan by components is in [docs/roles](roles/README.md).

Section 2 lists the completed work with dates confirmed by commits, and section 3 gives the plan. If the plan dates move, the change and its reason are recorded here.

## 1. Milestones

| Date | Milestone | What is submitted | Tag |
|---|---|---|---|
| 24.10.2026 | Pre-defence 1 | Analysis, requirements, architecture, prototype, evaluation plan, working version, stage 1 evaluation | `pre-defense-1` |
| January 2027 (date set by the School schedule) | Pre-defence 2 | Chapters 1–2, stage 2 evaluation, fixes after the comments | `pre-defense-2` |
| May 2027 (date set by the School schedule) | Final pre-defence | Full text, plagiarism check, presentation and demo | `final-pre-defense` |
| May – June 2027 | Defence | — | — |

## 2. Completed work: October 2026

| Date | What was done | Evidence |
|---|---|---|
| 07.10.2026 | Requirements for pre-defence 1 received | School document |
| 07–18.10.2026 | The topic and the "Justification of the feasibility of the diploma work" were sent to the supervisor and approved. The justification contains the topic in Russian and English, objectives and stages, methods and technologies, the expected result and the supervision plan (weekly meetings, milestones until May 2027) | The justification document (kept by the author and not included in the repository because it contains personal data) |
| 19.10.2026 | Repository: README, plan by 8 roles, component contracts | `0c38487` |
| 19.10.2026 | Environment and CI (role 1), demo database (2), backend API (3), SQL validator (4), LangGraph agent (5), web interface (6), logo and brand | `ead1c13` … `36c1df1` |
| 20.10.2026 | CI and interface accessibility fixes; Spider and BIRD loaded into PostgreSQL, datasets built | `9f91216`, `7490809` |
| 21.10.2026 | Stage 1 evaluation: experiments 1–2 and security, `EVALS.md` | `9fa9b82` |
| 21–23.10.2026 | Pre-defence documents: architecture and ADRs, proposal, requirements, literature review, comparisons, diagrams, roadmap; Figma prototype; YouTrack tasks | Pull requests in the repository |
| 24.10.2026 | Pre-defence 1 | Tag `pre-defense-1` |

The first commit added the plan by roles and the contracts between components, and the following commits added roles 1–6, implemented according to this plan. Since 22.10.2026 the work has been organised through YouTrack tasks, branches and pull requests.

In the plan of the justification document, the prototype (MVP) was scheduled for December 2026 – January 2027, and the clarification module and the experiments for February – March 2027. These stages were completed in October 2026, so the plan was revised: the freed time goes to user research, the second stage of the evaluation, fixes based on the first stage, and the diploma text (section 3).

## 3. Plan: October 2026 – May 2027

| Period | Work | Result | Requirements |
|---|---|---|---|
| 25.10 – 08.11.2026 | Comments from pre-defence 1; 3–5 interviews with potential users; refinement of the requirements based on them | Interview notes, requirements v2 | — |
| 09.11 – 30.11.2026 | Prompt v2: false refusals, defaults during clarification, "schema" ambiguity, protection of the explanation against injection. Check on questions not used in the analysis. Draft of chapter 1 (review) | `EVALS.md` v2, chapter 1 | FR-11, FR-16, NFR-02, NFR-07 |
| 01.12 – 27.12.2026 | Stage 2 evaluation: full samples Spider 200 and BIRD 150, a second seed, experiments 3–5, labelling by a second person (κ), classification of 30–50 errors | Full `EVALS.md` | FR-11, NFR-07 |
| January 2027 | Chapter 2 (design); preparation for and holding of pre-defence 2 | Tag `pre-defense-2` | — |
| February 2027 | Chapter 3 (implementation); optionally an MCP server with the validator tools | Draft of chapter 3 | FR-17 |
| March 2027 | Chapter 4 (experiments); abstract for a student conference on experiment 2 | Draft of chapters 1–4 | — |
| April 2027 | User testing with real users; full text; plagiarism check | Diploma text | — |
| May 2027 | Final pre-defence, fixes, presentation, demo scenario and backup video | Tag `final-pre-defense` | — |

## 4. Risks

| # | Risk | Likelihood | Impact | Measure | Status |
|---|---|---|---|---|---|
| R1 | The agent does not outperform the baseline on strict EX | High (happened in stage 1) | High: one of the hypotheses is not confirmed | Error analysis, relaxed EX, prompt v2 checked on held-out questions; an honest description of the negative result | Active |
| R2 | The LLM API becomes unavailable or more expensive | Medium | High | Fallback provider (Anthropic), response cache in the evaluation, a stub for tests and e2e | Under control |
| R3 | Budget for the experiments | Medium | Medium | LLM cache, subsets in stage 1, stage 2 estimate (≈ $9) | Under control |
| R4 | The simulated user distorts the effect of clarification | Medium | Medium | A judge on a strong model, review of "suspicious" answers, user testing in April | Active |
| R5 | The `ambiguous_ru` labels were checked by one person | High | Medium | A second annotator on 20% of the questions, Cohen's κ | Planned |
| R6 | No confirmation of the need from real users | High | Medium | 3–5 interviews by 08.11.2026 | Planned |
| R7 | Indirect injections through data | Medium (1 of 6 in stage 1) | Medium: the data does not change, but the answer text is distorted | Checking the numbers in the explanation → blocking, a separate prompt | Active |
| R8 | A single developer: illness, workload from other courses | Medium | High | Prioritisation (Must first), weekly progress checks with the supervisor, spare time in December and April | Under control |
| R9 | API changes in libraries (LangGraph, Next.js) | Low | Medium | Versions pinned in lock files, CI on every push | Under control |

## 5. Dependencies

- The stage 2 experiments depend on prompt v2, and prompt v2 depends on the stage 1 error analysis.
- Chapter 4 depends on the completion of the stage 2 evaluation.
- User testing depends on the interviews: the scenarios are chosen based on them.
- External: the OpenAI API (key and budget), Langfuse Cloud, access of the supervisor and the committee to the repository.
