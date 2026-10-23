# Prototype and main scenarios

The interface is already implemented, so the Figma prototype is assembled from screens of the working version (captured on 22.10.2026 on the demo database with the real agent). The interface language is Russian, and the frame and flow names in Figma are in Russian too.

- Clickable prototype: [Figma, flow S3 "Question with clarification"](https://www.figma.com/proto/M1KIz4KLirQv3UrLMaCJO4?node-id=1-3&starting-point-node-id=1%3A3)
- File: [Suhbat2DB prototype](https://www.figma.com/design/M1KIz4KLirQv3UrLMaCJO4) (pages "Сценарии" (Scenarios) and "Prototype")

## Scenarios

| # | Scenario | Screens | Requirements |
|---|---|---|---|
| S1 | Login and overview | 01 → 02 | FR-01, FR-15 |
| S2 | Connecting a data source (administrator) | 03 | FR-03, FR-04 |
| S3 | Ambiguous question → clarification → answer | 04 → 05 → 06 → 07 | FR-06, FR-07 |
| S4 | Checking the answer: table, SQL, five-level report | 07 → 08 → 09 → 10 | FR-09, FR-12 |
| S5 | Attack → refusal | 11 | NFR-01 |
| S6 | Phone and dark theme | 12, 13 | NFR-12 |

## Screens

| File | Screen |
|---|---|
| [01_login.png](screens/01_login.png) | Login |
| [02_overview.png](screens/02_overview.png) | Overview: query statistics, where the validator stopped SQL, ratings |
| [03_datasources.png](screens/03_datasources.png) | Data sources: indexing status, schema |
| [04_new_chat.png](screens/04_new_chat.png) | New dialogue with sample questions |
| [05_agent_progress.png](screens/05_agent_progress.png) | Agent progress in real time |
| [06_clarification.png](screens/06_clarification.png) | Clarification: what to count as "sales" (revenue, number of orders or units) and whose region to use for "by region" (customer's or manager's) |
| [07_answer_chart.png](screens/07_answer_chart.png) | Answer: explanation, result card, chart in the analysis panel |
| [08_answer_table.png](screens/08_answer_table.png) | Table tab |
| [09_answer_sql.png](screens/09_answer_sql.png) | SQL tab with the history of attempts |
| [10_answer_validation.png](screens/10_answer_validation.png) | Validation tab: the five validator levels |
| [11_refusal.png](screens/11_refusal.png) | Refusal: an attempt to drop a table is recognised as an unsafe request |
| [12_mobile_chat.png](screens/12_mobile_chat.png) | Dialogue on a phone (390 × 844) |
| [13_dark_chat.png](screens/13_dark_chat.png) | Dark theme |

## How the prototype works

The **Prototype** page contains 13 frames (12 × 1440 × 900 and 1 × 390 × 844) with clickable areas on top of the screenshots. The main flow S3 "Question with clarification" starts at screen 01: login → overview → new dialogue → question → agent progress (automatic transition after 1.5 s) → clarification → answer. On the answer screens the Chart, Table, SQL and Validation tabs work, the question field leads to the refusal screen, and the menu on the left is available on all application screens. The flows S6 "Phone" and S6 "Dark theme" start at screens 12 and 13; from them the user can go to the overview, a new dialogue and the data sources.

The **Сценарии** (Scenarios) page groups the screens by the scenarios S1–S6 with the related requirements.
