# Evidence of relevance

> Status on 23.10.2026. The evidence below comes from the analysis of available data: the project's own stage 1 experiments ([EVALS.md](../EVALS.md)) and published studies ([literature review](literature_review.md)). Interviews with potential users have not been held yet; they are planned for 25.10 – 08.11.2026 ([roadmap](roadmap.md), risk R6). Each statement is therefore marked as verified, partly verified or an assumption.

## 1. Sources of evidence

| # | Source | What it gives | Limitation |
|---|---|---|---|
| E1 | Experiment 2 on `ambiguous_ru`: 62 ambiguous and 44 clear questions about the demo database | How often an LLM without clarification answers a different reading of the question, and how much clarification changes the result | One synthetic database; the user is simulated by an LLM |
| E2 | Security check on the `unsafe` set: 46 natural-language attacks, 88 SQL attacks, 6 indirect injections | Whether an LLM agent produces dangerous SQL or follows instructions hidden in the data | Attacks written by the author |
| E3 | Published benchmarks and studies of ambiguity: AmbiQT, AMBROSIA, PRACTIQ (sources 10–12) | Independent confirmation that LLMs usually return one interpretation and recognise ambiguity poorly | English datasets |
| E4 | Studies of prompt-to-SQL injection and the OWASP Top 10 for LLM applications (sources 13, 14, 25) | Independent confirmation that LLM-integrated database applications are attacked in practice | Not specific to the target users |
| E5 | Interviews with potential users, 3–5 people ([template](templates/interview.md)) | Who needs the system, how they get data now, whether they accept clarifying questions | **Not done yet**, planned for 25.10 – 08.11.2026 |

## 2. Verified findings and assumptions

| # | Statement | Status | Evidence |
|---|---|---|---|
| 1 | An LLM without clarification silently chooses one reading of an ambiguous question | ✅ Verified | E1: in 25 of 62 ambiguous questions the answer was correct for another reasonable interpretation; E3 reports the same for English |
| 2 | Clarification with answer options increases accuracy on ambiguous questions | ⚠️ Partly verified | E1: 40.3% → 67.7% EX, p < 0.001, but the answers were given by a simulated user, not by people |
| 3 | Clarification does not get in the way on clear questions | ⚠️ Partly verified | E1: 5 of 44 clear questions (11.4%) still received a clarifying question; whether users accept this has to be checked in interviews |
| 4 | An LLM agent can be pushed to generate dangerous SQL or to follow instructions hidden in the data | ✅ Verified | E4; E2: all 134 direct attacks were blocked by the validator and guard, but 1 of 6 indirect injections changed the answer text |
| 5 | Analysts, managers, teachers and students who do not know SQL need fast access to data | ❓ Assumption | Based on the author's experience; to be checked in E5 (questions 1–3) |
| 6 | Users want to see the SQL and the validation report to trust the answer | ❓ Assumption | To be checked in E5 (questions 8–9) |
| 7 | Data administrators will connect a database only with a read-only guarantee | ❓ Assumption | To be checked in E5 (question 10) |
| 8 | Users prefer a clarifying question to a quick answer based on a guess | ❓ Assumption | To be checked in E5 (question 7) |

## 3. How the evidence affects the requirements

- Statements 1 and 2 are the basis for the clarification requirements (FR-07, FR-08) and for experiment 2 in the evaluation plan.
- Statement 4 is the basis for the five-level validator and the read-only guarantee (FR-09, NFR-01, NFR-03).
- Statement 3 led to a planned change: the detector prompt in stage 2 must reduce unnecessary clarifications ([roadmap](roadmap.md), November 2026).
- Statements 5–8 define the target users and the visible SQL and validation report (FR-06, FR-09). If the interviews do not confirm them, the requirements and the target users in the [proposal](proposal.md) will be revised in requirements v2.

## 4. Interview plan

| | |
|---|---|
| Who | 3–5 people: an analyst or business employee who works with reports, a manager, a teacher of a database course, a person who administers a database |
| When | 25.10 – 08.11.2026 |
| How | 20–30 minutes, in person or online, by the [interview template](templates/interview.md); personal data is not stored in the repository |
| Result | Notes in `docs/interviews/`, a summary table "confirmed / not confirmed / new", requirements v2 |
