# Роль 5. AI Agent (LLM Engineer)

**Цель:** LangGraph-агент, который заменяет `FakeAgentRunner`. Агент связывает вопрос со схемой, уточняет неоднозначности, генерирует SQL, исправляет его по отчёту валидатора, выполняет и поясняет результат. Каждый шаг трассируется.
**Зависит от:** роли 3 (интерфейс `AgentRunner`, `SchemaSnapshot`), 4 (валидатор).
**Нужно для:** Frontend (реальные события), Evals (конфигурации `agent` и `baseline`).

Граф и состояние описаны в README §5 и в [`CONTRACTS.md` §5](../CONTRACTS.md#5-состояние-агента-langgraph).

## Задачи

Задачи упорядочены так, чтобы **baseline был готов первым**: с ним сравниваются все улучшения.

### 5.1 Слой LLM
- [ ] Абстракция `LLMClient` с реализациями для Anthropic и OpenAI (через `langchain-anthropic` / `langchain-openai` или нативные SDK)
- [ ] Конфиг для каждого узла: `model`, `temperature`, `max_tokens`, `timeout`. По умолчанию:

  | Узел | Модель | temperature | Почему |
  |---|---|---|---|
  | `guard_input` | дешёвая | 0 | Бинарная классификация |
  | `detect_ambiguity` | сильная | 0 | Нужно рассуждение о схеме |
  | `generate_sql` | сильная | 0 (подбирается в A/B) | Точность важнее разнообразия |
  | `explain_and_visualize` | дешёвая | 0.3 | Короткий текст по готовым числам |

- [ ] Structured output (Pydantic) для всех узлов-классификаторов
- [ ] **Fallback:** при ошибке, таймауте или 429 основного провайдера выполняется повтор на резервном. Счётчик стоимости запроса и лимит `LLM_MAX_COST_PER_REQUEST`
- [ ] Langfuse callback / `@observe` на всех вызовах, `trace_id` передаётся в SSE `done`

### 5.2 Retrieval: schema linking
- [ ] `SchemaIndexer.index(snapshot)` (реализация интерфейса из роли 3):
  - карточка таблицы: `table: orders — Заказы покупателей. Columns: id, customer_id → customers.id, …`
  - карточка столбца: `orders.total_amount (numeric) — Сумма заказа в тенге с учётом скидок`
  - коллекции `schema_elements`, `column_values`, `sql_examples`, payload `{datasource_id, type, table, column}`
- [ ] Эмбеддинги: выбор модели по recall@k на 30–50 вопросах (кандидаты: `text-embedding-3-small`, `bge-m3`, `multilingual-e5-large`). Результат сравнения записывается в `EVALS.md`
- [ ] Гибридный поиск: dense + sparse (BM25) в Qdrant, объединение через **RRF** (k = 60). Фильтр по `datasource_id`
- [ ] Расширение по FK: к найденным таблицам добавляются соседи на 1 шаг, чтобы были доступны пути `JOIN`
- [ ] Value linking: сущности из вопроса («Алматы», «Kaspi») ищутся в `column_values`
- [ ] Сборка `linked_schema` в компактный DDL-подобный текст с комментариями и 2–3 значениями (Just-in-Time context)
- [ ] Метрика: **schema recall@k** (доля таблиц эталонного SQL, попавших в `linked_schema`). Цель ≥ 0.95

### 5.3 Baseline (для сравнения)
- [ ] `BaselineRunner`: полная схема + вопрос → SQL одним вызовом → выполнение без валидации и самокоррекции (только уровни 2 и 5, чтобы не испортить данные). Используется только в evals

### 5.4 Граф: каркас
- [ ] `StateGraph(AgentState)` со всеми узлами из README §5, сначала в виде заглушек
- [ ] Маршрутизация **только в Python route-функциях** по полям состояния
- [ ] Лимиты: `attempts ≤ AGENT_MAX_CORRECTIONS` (3), `clarification_rounds ≤ 2`
- [ ] `PostgresSaver` (checkpointer) на `app-db`, `thread_id = session_id`
- [ ] `LangGraphAgentRunner`: `astream` графа → преобразование в SSE-события из CONTRACTS §2
- [ ] Визуализация графа (`get_graph().draw_mermaid()`) сохраняется в `docs/graph.md`

### 5.5 Узлы генерации и самокоррекции
- [ ] `generate_sql`: промпт v1 из блоков роль → задача → схема (`linked_schema`) → few-shot (2–4 из `sql_examples`) → уточнения пользователя → правила (только PostgreSQL `SELECT`, явные `JOIN`, алиасы таблиц) → формат. Ответ в виде structured output `{sql, reasoning_short}`
- [ ] Промпты хранятся в Langfuse Prompt Management с версиями, в коде есть fallback-копия
- [ ] `validate_sql` вызывает `validator.validate` + `explain`. `fatal` → `refuse`
- [ ] `self_correct`: в контекст генератора добавляются **прошлый SQL + отчёт валидатора (уровень, message, hint) или ошибка СУБД**. Без этого повтор воспроизводит ту же ошибку
- [ ] `execute` вызывает `validator.execute_readonly`

### 5.6 Неоднозначность и уточнение
- [ ] `detect_ambiguity`: вход — вопрос, `linked_schema`, прошлые `clarifications` сессии; выход — `AmbiguityVerdict` (README §6)
- [ ] Варианты уточнения **обязательно ссылаются на реальные столбцы и значения** (`orders.total_amount`, `COUNT(orders.id)`), а не на абстракции
- [ ] Промпт содержит few-shot примеры однозначных вопросов, чтобы снизить over-clarification
- [ ] `clarify`: `interrupt(ClarificationRequest)` → SSE `clarification` → `resume` с ответами → `resolved_question`
- [ ] Память сессии: уже выбранные интерпретации («квартал = календарный») применяются автоматически и показываются пользователю в ответе («Использован календарный квартал»)

### 5.7 Guard и пояснение
- [ ] `guard_input`: классификация `{safe, in_scope, category}`. Prompt injection, просьбы изменить данные и вопросы вне БД → `refuse` с вежливым объяснением
- [ ] Комментарии схемы и значения из БД передаются в промпты внутри `<untrusted_data>`
- [ ] `explain_and_visualize`:
  - **тип графика выбирает код** по типам столбцов (дата + число → `line`, категория + число → `bar`, ≤ 6 категорий долей → `pie`, одно значение → `none`)
  - LLM пишет 2–4 предложения резюме, **числа берутся только из `result`**; результат передаётся усечённым (≤ 50 строк)
  - пост-проверка: каждое число в тексте ищется в `result` (кодом), несовпадение логируется как предупреждение в trace

### 5.8 Тесты
- [ ] Юнит-тесты route-функций (все ветви)
- [ ] Интеграционные тесты графа с фиктивным LLM (`FakeListChatModel`): ветки самокоррекции, исчерпания лимита, уточнения и resume, отказа
- [ ] Smoke-тест с реальным LLM на 10 вопросах (запускается вручную и в `eval-smoke`)

## Definition of Done
- `FakeAgentRunner` заменён, все SSE-события соответствуют CONTRACTS §2
- Демо-сценарий «Покажи продажи за прошлый квартал по регионам» → уточнение → ответ с графиком проходит end-to-end
- В Langfuse виден полный trace с узлами, токенами и стоимостью
- Schema recall@k ≥ 0.95 на dev-наборе
- Промпты v1 и текущий сохранены в Langfuse (для слайда «эволюция промпта»)

## База знаний
- `ai_engineering.md` §2.3, §5 (StateGraph, route_fn, reducers), §6 (self-reflection), §7 (HITL + checkpointer), §2.6 (модель на узел), §12 (failure modes)
- `rag.md` §2.3–2.4 (эмбеддинги, hybrid + RRF), §7 (метрики retrieval)
- `prompting_memory_tools.md` §2.1–2.3 (промптинг, Just-in-Time), §5.5 (Text-to-SQL pipeline)
- `ai_security.md` §4.3–4.4 (untrusted data, guardrail на входе)
