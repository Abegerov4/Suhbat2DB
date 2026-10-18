# Граф агента (LangGraph)

Сгенерировано из кода: `build_graph(...).get_graph().draw_mermaid()` ([backend/app/agent/graph.py](../backend/app/agent/graph.py)).
Пунктир — условные переходы: маршрут выбирает route-функция по полю `state["route"]`, а не LLM.

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

| Узел | Что делает | Модель |
|---|---|---|
| `guard_input` | Классификация: вопрос о данных / изменение данных / prompt injection / вне темы | fast |
| `schema_linking` | Гибридный поиск по схеме, достройка путей JOIN по внешним ключам, few-shot примеры | — (эмбеддинги) |
| `detect_ambiguity` | Однозначен ли вопрос; варианты трактовок привязаны к столбцам схемы | strong |
| `clarify` | `interrupt()`: граф ждёт ответа пользователя, затем продолжает с checkpoint | — |
| `generate_sql` | SQL по связанной схеме, примерам, контексту диалога и ошибкам прошлых попыток | strong |
| `validate_sql` | Уровни 1–4 валидатора ([validator.md](validator.md)) | — |
| `self_correct` | Фиксирует ошибку попытки; лимит — `AGENT_MAX_CORRECTIONS` (3) | — |
| `execute` | Уровень 5: выполнение в read-only транзакции | — |
| `explain_and_visualize` | Тип графика — кодом, пояснение — LLM (стриминг), проверка чисел | fast |
| `refuse` | Вежливый отказ с кодом причины | — |
