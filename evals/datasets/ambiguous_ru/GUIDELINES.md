# Labelling guidelines for `ambiguous_ru`

The set checks whether the agent can tell an ambiguous question from a clear one and answer correctly after clarification. The database is the demo database ([docs/demo_db.md](../../../docs/demo_db.md)). The set is generated and checked by the script [`backend/evals/build_ambiguous.py`](../../../backend/evals/build_ambiguous.py); editing the JSONL by hand is not allowed. The questions are in Russian; the examples below give an English translation.

## Format

```json
{"id": "ambiguous_ru-amb-001", "question": "Покажи продажи за 2025 год", "is_ambiguous": true,
 "ambiguity_types": ["metric"], "target": 0,
 "interpretations": [
   {"answer_to_clarification": "выручка — сумма заказов без отменённых", "gold_sql": "SELECT ..."},
   {"answer_to_clarification": "количество заказов без отменённых", "gold_sql": "SELECT ..."}]}
```

- `interpretations` lists all reasonable interpretations with their reference SQL; a clear question has one interpretation and `answer_to_clarification = null`.
- `target` is the interpretation the user "had in mind". The simulated user chooses it, and the agent's answer is compared with its reference. The intended interpretation alternates and is not always the first one; otherwise an agent that simply applies a default would get an inflated EX.

## When a question is ambiguous

A question is ambiguous only if **both** conditions hold:

1. There are at least two reasonable interpretations that an expert on this database would choose without a hint.
2. The interpretations give **different answers on this data**. This is checked automatically: the script runs all the references and rejects the set if two of them match.

Types (`ambiguity_types`), following the classification in the agent prompt:

| Type | Example | Interpretations |
|---|---|---|
| `metric` | «Покажи продажи за 2025 год» ("Show sales for 2025") | revenue / number of orders / units sold |
| `temporal` | «Выручка за первый квартал 2026 года» ("Revenue for Q1 2026") | calendar / fiscal quarter (FY starting on 1 April) |
| `temporal` | «Сколько денег мы получили в сентябре 2026?» ("How much money did we receive in September 2026?") | by payment date / by order date |
| `value` | «Выручка в Алматы за 2025 год» ("Revenue in Almaty for 2025") | the city / the city together with Almaty region |
| `scope` | «Кто лучший менеджер за 2025 год?» ("Who is the best manager for 2025?") | by revenue / by number of orders |
| `scope` | «Сколько у нас клиентов?» ("How many customers do we have?") | registered / have bought / active |
| `schema` | «Средняя цена проданных смартфонов» ("Average price of smartphones sold") | `order_items.unit_price` / `products.price` |

## When a question is clear

Clear questions follow **the same defaults that the agent knows** (the `ambiguity.md` prompt). Otherwise an agent error would be a labelling error:

- "revenue" is the sum of `orders.total_amount`, and cancelled orders (`status = 'cancelled'`) are excluded;
- "for 2025" without the word "fiscal" means the calendar year;
- "orders placed" means all orders, including cancelled ones;
- if the question explicitly names the measure, the type of period or the boundary of the selection ("by revenue", "fiscal", "including cancelled", "the city of Almaty without the region"), the question is clear.

## General rules

- **Absolute dates only.** Questions such as "for last quarter" are not used: their answer depends on the day of the run, and the runs would stop being reproducible.
- **One reference SQL per interpretation.** It is run on the full volume of the demo database (`make seed`, SCALE=1.0) and must return a non-empty result.
- **No leakage into few-shot.** The wording does not match the agent's examples (`backend/app/agent/examples/demo.json`); near-copies were replaced during the build.
- **Row order** is taken into account only when the outer query of the reference has `ORDER BY` ("top N").

## Second check of the labels

20% of the questions (21) are checked by a second person, the supervisor or a fellow student:

```bash
cd backend && uv run python -m evals.kappa export   # review_sample.csv: questions only, random order
# the second annotator fills in reviewer_ambiguous (yes/no) and reviewer_types
cd backend && uv run python -m evals.kappa score    # Cohen's κ → review_result.json
```

The annotator sees only the question text: the export contains neither ids (they include `amb`/`clear`) nor interpretations. The mapping of numbers to questions is kept in `review_key.json`. Agreement κ ≥ 0.6 is considered acceptable. Disagreements are analysed and described in `EVALS.md`.
