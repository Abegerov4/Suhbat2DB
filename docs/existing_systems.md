# Comparison of existing systems

> The data comes from public documentation, engineering blogs, vendor forums and academic publications as of 22.10.2026; the links are at the end of the document. The systems were not tested by hand. "Not stated" means that the sources found give no confirmation; the feature may still exist. The cells about clarification (C1) and the Vanna licence were checked against the sources again on 23.10.2026.

## 1. Systems

| System | What it is | Why it was chosen |
|---|---|---|
| Snowflake Cortex Analyst | A service of the Snowflake platform: question → SQL over a semantic model (YAML) | A large commercial system that handles ambiguity explicitly |
| Databricks AI/BI Genie | A conversational interface to Databricks tables in a configured Genie space | The second large "data + LLM" system |
| ThoughtSpot Spotter | AI analyst of the ThoughtSpot BI platform | The BI approach: search tokens instead of SQL |
| Vanna | An open-source Python library: RAG over DDL, documentation and SQL examples | The closest open analogue that can be self-hosted |
| Chat with an LLM (ChatGPT and similar, without tools) | The user pastes the schema and asks for SQL | The most common way in practice; corresponds to the baseline in the experiments |

The subsection "Research systems" below separately covers two research prototypes with a clarification dialogue, Sphinteract and AmbiSQL. They are the closest academic analogues ([literature review](literature_review.md), sources 18 and 20), but they are not products, so they are compared only on the criteria that apply to them.

## 2. Criteria

| # | Criterion | Why it matters for the task |
|---|---|---|
| C1 | Ambiguity detection and clarification | Main problem 2 in the [proposal](proposal.md#1-problem) |
| C2 | SQL visible to the user | The user can check how the answer was obtained |
| C3 | Deterministic SQL validation before execution | Protection against wrong and dangerous queries |
| C4 | Read-only guarantee | The model cannot change the data |
| C5 | Works without a manually built semantic model | Questions can be asked right after the database is connected |
| C6 | Open source and self-hosting | The data does not leave the organisation |
| C7 | Any PostgreSQL database as a source | A typical DBMS at universities and small businesses |
| C8 | Russian interface and questions | The target users |
| C9 | Quality measured on open datasets | Whether the accuracy claims can be checked |

## 3. Comparison

### 3.1 Products and practical solutions

| Criterion | Cortex Analyst | Genie | Spotter | Vanna | Chat with an LLM | Suhbat2DB |
|---|---|---|---|---|---|---|
| C1. Clarification | Partly. An ambiguous question is rejected with a list of similar questions the system can answer [S2] | Partly. Can ask a clarifying question; according to the forum, this is configured through the space instructions [G2, G3] | Yes, "Asks when it is not sure instead of guessing" [T1] | — not stated | Partly. Depends on the model, not guaranteed | Yes. A question with options tied to the schema, pause and resume (ADR-023) |
| C2. SQL visible | Yes. The API returns an `sql` block [S1] | Yes. The generated SQL can be viewed [G2] | Partly. Shows search tokens and natural-language steps [T1, T2] | Yes | Yes | Yes. With the history of attempts |
| C3. SQL validation | — not stated (quality comes from the semantic model and verified queries) [S3] | — not stated (trusted queries and functions from the space author) [G1] | Partly. The search engine builds the SQL from tokens [T2] | — not stated | No | Yes, 5 levels, AST, EXPLAIN ([validator.md](validator.md)) |
| C4. Read-only | Partly. Depends on the Snowflake role privileges | Partly. Depends on the privileges in Unity Catalog | Partly. BI platform privileges | Partly. Depends on the connection passed by the developer | No. The user runs the SQL personally | Yes. Privilege check on connection + read-only transaction + AST policy |
| C5. No manual semantic model | No. Needs a semantic model or a view [S1] | Partly. The space must be configured: tables, instructions, examples [G1] | No. Needs a ThoughtSpot data model | Partly. Needs "training" on DDL, documentation, examples [V1] | Yes | Yes. The schema, comments and values are indexed automatically |
| C6. Open source, self-hosted | No. Snowflake cloud | No. Databricks cloud | No. SaaS | Yes. MIT, maintained (version 2.0.2, February 2026) [V1] | No | Yes, docker compose |
| C7. Any PostgreSQL | No. Data in Snowflake | No. Data in Databricks | Partly. Through platform connectors | Yes | Yes | Yes |
| C8. Russian | — not stated | — not stated | — not stated | Partly. Depends on the model | Yes | Yes. Interface and prompts in Russian; the `ambiguous_ru` set |
| C9. Open evaluation | Partly. Internal measurements in a blog post [S2] | — not stated | — not stated | — not stated | — (there is work on the models themselves) | Yes. Spider, BIRD, `ambiguous_ru`, `unsafe` with intervals ([EVALS.md](../EVALS.md)) |

Notation: "Yes" means the feature is present; "Partly" means it is present partly or with conditions; "No" means it is absent; "—" means it is not stated in the sources found.

### 3.2 Research systems

| Criterion | Sphinteract | AmbiSQL | Suhbat2DB |
|---|---|---|---|
| C1. Clarification | Yes. Short questions with options and a free answer, then the SQL is rebuilt; four ambiguity types [R1] | Yes. Multiple-choice questions, question rewriting; taxonomy by database elements and by model reasoning [R2] | Yes. Options tied to schema columns, graph pause and resume |
| C3. SQL validation | — not stated | — not stated | Yes, 5 levels, AST, EXPLAIN |
| C4. Read-only | — not stated | — not stated | Yes. Role privileges, read-only transaction, AST policy |
| C6. Open source | — not stated | Yes. The code is published on GitHub [R2] | Yes |
| C8. Russian | No. English datasets | No. English datasets | Yes |
| C9. Measured quality | Yes. KaggleDBQA and BIRD; the user is mostly simulated by an LLM [R1] | Partly. Ambiguity detection accuracy and the gain in exact SQL match on its own evaluation; a demo paper [R2] | Yes. Spider, BIRD, `ambiguous_ru`, `unsafe` |

Both prototypes show that clarification with answer options increases accuracy. They do not cover SQL validation before execution or a read-only guarantee: these are works about understanding the question, not about executing the query safely.

## 4. Conclusions

The commercial platforms handle ambiguity through configuration. Cortex Analyst rejects an ambiguous question, and Genie and Cortex rely on a semantic model and verified queries that a specialist prepares in advance. This is enough for typical questions, but the platform has to be configured by hand, and the data has to be stored in it.

Spotter is the closest in behaviour: it clarifies the question when it is not sure. However, it is a closed product, and it works only inside its own BI platform with its own data model.

Vanna generates SQL with RAG, but its description says nothing about clarification, SQL validation or a read-only guarantee.

Chat with an LLM is the most accessible and the most risky option: nobody checks the SQL, and the user moves it to the DBMS personally. This option is used as the baseline in the experiments.

The research prototypes Sphinteract and AmbiSQL address the same clarification task as the project, but separately from SQL validation and safe execution, and only for English.

Suhbat2DB fills the gap between them. It is an open system for any PostgreSQL database that does not need a manual semantic model. It clarifies an ambiguous question, checks every SQL query deterministically, guarantees read-only access at the level of DBMS privileges, and its quality is measured on open datasets in a way that can be repeated.

The commercial systems have features that the project lacks: a semantic layer with business metrics maintained by analysts, scaling, row-level access control and support for other DBMSs. Some of these can be added later.

## Sources

- [S1] Snowflake. [Cortex Analyst](https://docs.snowflake.com/user-guide/snowflake-cortex/cortex-analyst); [REST API](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/rest-api)
- [S2] Snowflake Engineering Blog. [Snowflake Cortex Analyst: Behind the Scenes](https://www.snowflake.com/en/engineering-blog/snowflake-cortex-analyst-behind-the-scenes/)
- [S3] Snowflake. [Optimize a semantic view or model with verified queries](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/analyst-optimization)
- [G1] Databricks. [Use trusted assets in AI/BI Genie spaces](https://docs.databricks.com/en/genie/trusted-assets.html)
- [G2] Databricks Community. [Can Genie ask clarifying questions?](https://community.databricks.com/t5/generative-ai/can-genie-ask-clarifying-questions/m-p/125575)
- [G3] Databricks. [Knowledge store](https://docs.databricks.com/en/genie/knowledge-store)
- [T1] ThoughtSpot. [Best practices for prompting Spotter](https://docs.thoughtspot.com/cloud/latest/spotter-business)
- [T2] ThoughtSpot. [Spotter documentation](https://docs.thoughtspot.com/cloud/latest/spotter)
- [V1] Vanna. [PyPI: vanna](https://pypi.org/project/vanna/)
- [R1] Zhao F. et al. [Sphinteract: Resolving Ambiguities in NL2SQL Through User Interaction](https://www.vldb.org/pvldb/vol18/p1145-zhao.pdf). PVLDB 18(4), 2024
- [R2] Ding Z. et al. [AmbiSQL: Interactive Ambiguity Detection and Resolution for Text-to-SQL](https://arxiv.org/abs/2508.15276). SIGMOD 2026 demo; [code](https://github.com/JustinzjDing/AmbiSQL)
