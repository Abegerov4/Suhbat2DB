# Agent graph (LangGraph)

Generated from the code: `build_graph(...).get_graph().draw_mermaid()` ([backend/app/agent/graph.py](../backend/app/agent/graph.py)).
Dashed lines are conditional transitions: a route function chooses the route from the `state["route"]` field; the LLM does not choose it.

```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	guard_input(guard_input)
	schema_linking(schema_linking)
	detect_ambiguity(detect_ambiguity)
	clarify(clarify)
	generate_sql(generate_sql)
	validate_sql(validate_sql)
	self_correct(self_correct)
	execute(execute)
	explain_and_visualize(explain_and_visualize)
	refuse(refuse)
	__end__([<p>__end__</p>]):::last
	__start__ --> guard_input;
	clarify --> schema_linking;
	detect_ambiguity -.-> clarify;
	detect_ambiguity -. &nbsp;generate&nbsp; .-> generate_sql;
	detect_ambiguity -.-> refuse;
	execute -. &nbsp;explain&nbsp; .-> explain_and_visualize;
	execute -.-> refuse;
	execute -. &nbsp;retry&nbsp; .-> self_correct;
	generate_sql -.-> refuse;
	generate_sql -. &nbsp;validate&nbsp; .-> validate_sql;
	guard_input -.-> refuse;
	guard_input -. &nbsp;ok&nbsp; .-> schema_linking;
	schema_linking --> detect_ambiguity;
	self_correct --> generate_sql;
	validate_sql -.-> execute;
	validate_sql -.-> refuse;
	validate_sql -. &nbsp;retry&nbsp; .-> self_correct;
	explain_and_visualize --> __end__;
	refuse --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```

| Node | What it does | Model |
|---|---|---|
| `guard_input` | Classification: question about data / data change / prompt injection / off topic | fast |
| `schema_linking` | Hybrid search over the schema, completion of JOIN paths over foreign keys, few-shot examples | — (embeddings) |
| `detect_ambiguity` | Whether the question is clear; interpretation options are tied to schema columns | strong |
| `clarify` | `interrupt()`: the graph waits for the user's answer and then resumes from the checkpoint | — |
| `generate_sql` | SQL from the linked schema, examples, dialogue context and errors of earlier attempts | strong |
| `validate_sql` | Validator levels 1–4 ([validator.md](validator.md)) | — |
| `self_correct` | Records the error of the attempt; the limit is `AGENT_MAX_CORRECTIONS` (3) | — |
| `execute` | Level 5: execution in a read-only transaction | — |
| `explain_and_visualize` | Chart type chosen by code, explanation written by the LLM (streaming), check of the numbers | fast |
| `refuse` | Polite refusal with a reason code | — |
