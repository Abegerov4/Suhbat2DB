# Роль 3. Backend

**Цель:** FastAPI-сервис со всеми эндпоинтами из [`CONTRACTS.md`](../CONTRACTS.md). Вместо агента пока работает заглушка, которая отдаёт корректный SSE-поток.
**Зависит от:** роли 1 и 2.
**Нужно для:** SQL Validator (интроспекция схемы), AI Agent (точка запуска графа), Frontend (API).

## Задачи

### 3.1 Каркас
- [ ] Структура `backend/app/`: `api/`, `core/` (config, db, security), `models/`, `schemas/`, `services/`
- [ ] Async SQLAlchemy + `asyncpg`, dependency `get_db()`, lifespan для пулов соединений
- [ ] Единый обработчик ошибок в формате `{error: {code, message}}`
- [ ] Структурированные логи (`structlog`), `request_id` в каждом логе

### 3.2 Аутентификация
- [ ] Регистрация и логин, хэширование `argon2` (или `bcrypt`), JWT (`pyjwt`), TTL 24 ч
- [ ] Зависимости `current_user`, `require_role("admin")`
- [ ] Первый `admin` создаётся из env (`ADMIN_EMAIL`, `ADMIN_PASSWORD`) при старте

### 3.3 Источники данных
- [ ] `POST /datasources`: проверка подключения → **проверка, что роль действительно read-only** (`SHOW default_transaction_read_only` и пробный `CREATE TEMP TABLE`, который должен упасть). Если роль может писать, подключение отклоняется с кодом `datasource_not_readonly`
- [ ] Шифрование строки подключения (Fernet)
- [ ] **Интроспекция схемы** → `SchemaSnapshot` (см. CONTRACTS §4): `information_schema.columns`, `pg_constraint` для PK и FK, `pg_description` для комментариев, `pg_class.reltuples` для оценки числа строк
- [ ] `sample_values`: для текстовых столбцов с `n_distinct` ≤ 50 (из `pg_stats`) до 20 значений через `SELECT DISTINCT ... LIMIT 20`
- [ ] Фоновая задача индексации (FastAPI `BackgroundTasks` для MVP) меняет статус `indexing → ready | error`. Сама индексация в Qdrant реализуется в роли 5, здесь вызывается интерфейс `SchemaIndexer.index(snapshot)` с пустой реализацией
- [ ] Пул соединений к целевым БД кэшируется по `datasource_id`

### 3.4 Сессии и сообщения
- [ ] CRUD сессий, проверка владельца
- [ ] `POST /sessions/{id}/messages` сохраняет сообщение пользователя и возвращает `StreamingResponse` (`text/event-stream`)
- [ ] `POST /sessions/{id}/clarify` возвращает SSE и продолжает граф
- [ ] **Заглушка агента** `FakeAgentRunner`: отдаёт события `step → sql → validation ×5 → result → answer → chart → done` с задержками. По слову «продажи» в вопросе отдаёт `clarification`. Это позволяет фронтенду работать до готовности агента
- [ ] Интерфейс `AgentRunner` с методами `run(session_id, question)` и `resume(session_id, answers)`, оба возвращают `AsyncIterator[SSEEvent]`. В роли 5 заглушка заменяется на `LangGraphAgentRunner`
- [ ] По окончании потока сохраняется сообщение ассистента (`sql`, `validation_report`, `result_meta`, `chart_spec`, `trace_id`) и запись в `query_log`
- [ ] Отмена: если клиент закрыл соединение, выполнение прерывается

### 3.5 Обратная связь
- [ ] `POST /messages/{id}/feedback` сохраняет оценку в БД. В роли 5 добавляется отправка score в Langfuse по `trace_id`

### 3.6 Тесты
- [ ] pytest + `httpx.AsyncClient`, тестовая БД (testcontainers или сервис в CI)
- [ ] Тесты: auth (успех, неверный пароль, нет прав), datasource (read-only проверка отклоняет пишущую роль), интроспекция на демо-БД, SSE-поток заглушки заканчивается `done`

## Definition of Done
- Все эндпоинты из CONTRACTS §1 работают, Swagger на `/docs` актуален
- Демо-БД подключается через API, `GET /datasources/{id}/schema` возвращает полный снимок с комментариями и FK
- Подключение с пишущей ролью отклоняется
- SSE-заглушка проходит все сценарии из CONTRACTS §2, включая `clarification`
- Покрытие тестами `api/` и `services/` ≥ 70%

## База знаний
- `prompting_memory_tools.md` §4.1 (Just-in-Time: схема и несколько строк вместо всех данных, то есть `sample_values`)
- `ai_security.md` §2.3 (данные из БД, в том числе комментарии к столбцам, считаются untrusted)
