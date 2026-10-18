# Роль 2. Database

**Статус: ✅ выполнена** (октябрь 2026). Подробное описание демо-БД и её «ловушек» — в [docs/demo_db.md](../demo_db.md).

**Цель:** демонстрационная БД, на которой реально возникают неоднозначные вопросы, безопасная роль для агента и схема БД приложения.
**Зависит от:** роль 1 (контейнеры `app-db` и `target-db`).
**Нужно для:** Backend, SQL Validator, AI Agent, Evals.

## Задачи

### 2.1 Демо-БД (`target-db`)

Домен: **продажи розничной сети электроники и товаров для дома в Казахстане**. Его выбрали потому, что в нём естественно возникают все типы неоднозначности из README (§6).

| Таблица | Ключевые столбцы | Источник неоднозначности |
|---|---|---|
| `regions` | id, name, region_type | «Алматы» как город или вместе с областью (value) |
| `cities` | id, name, region_id | |
| `customers` | id, full_name, city_id, segment (`b2c`/`b2b`), is_active, registered_at | «клиенты»: все, покупавшие или активные (scope) |
| `managers` | id, full_name, region_id, hired_at, fired_at | «лучшие менеджеры»: по выручке или числу заказов, с уволенными или без (scope) |
| `categories`, `products` | id, name, category_id, price, cost, is_discontinued | текущая цена или цена продажи (schema) |
| `orders` | id, customer_id, manager_id, channel, status, created_at, discount_amount, total_amount | «продажи»: сумма или количество (metric); отменённые заказы; онлайн-заказы без менеджера |
| `order_items` | order_id, product_id, quantity, unit_price | «продажи» как проданные единицы (metric) |
| `payments` | id, order_id, paid_at, amount, method | дата заказа или дата оплаты (temporal); несколько платежей на заказ |
| `returns` | id, order_id, returned_at, amount, reason | выручка с учётом возвратов или без |
| `fiscal_calendar` | date, calendar_year/quarter, fiscal_year/quarter | **финансовый год начинается 1 апреля** (temporal) |

- [x] DDL в [`demo_db/schema.sql`](../../demo_db/schema.sql) с PK, FK, индексами и `CHECK` (в том числе `channel = 'online'` ⇔ `manager_id IS NULL`)
- [x] `COMMENT ON TABLE/COLUMN` на русском и английском для каждого объекта (проверяется тестом)
- [x] Генератор [`demo_db/seed.py`](../../demo_db/seed.py) (фиксированный seed, загрузка через `COPY`): 30k клиентов, 200 товаров, 100k заказов за 3 года, рост ~25% в год, сезонность, ~5% возвратов. Изначально планировалось 5k клиентов, но тогда на клиента приходилось ~20 заказов, а активными было 96% клиентов, что для магазина электроники неправдоподобно
- [x] «Ловушки» реального мира: отменённые заказы, `NULL` в `manager_id`, клиенты без заказов, уволенные менеджеры, оплата частями, оплата в другом квартале
- [x] Часовой пояс базы `Asia/Almaty`: кварталы и дни считаются по местному времени

### 2.2 Роль только для чтения
- [x] Роль `s2d_reader` ([`demo_db/roles.sql`](../../demo_db/roles.sql)): только `CONNECT`, `USAGE`, `SELECT`. У `PUBLIC` отозваны права на базу (включая `TEMP`) и на схему `public`
- [x] Ограничения сессии: `default_transaction_read_only`, `statement_timeout = 5s`, `idle_in_transaction_session_timeout`, `CONNECTION LIMIT 20`
- [x] Тесты: 17 опасных команд × 2 режима (`default_transaction_read_only` можно отключить из сессии, поэтому гарантию дают права, и это проверяется отдельно), `GRANT` без эффекта, тайм-аут `pg_sleep`, отсутствие привилегий у роли

### 2.3 БД приложения (`app-db`)

| Таблица | Столбцы |
|---|---|
| `users` | id (uuid), email (unique), password_hash, role (`admin`/`analyst`), created_at |
| `datasources` | id, owner_id → users, name, dialect, connection_encrypted, status, error, schema_snapshot (jsonb), indexed_at, created_at |
| `chat_sessions` | id (= LangGraph `thread_id`), user_id, datasource_id, title, created_at, updated_at |
| `messages` | id, session_id, role, content, sql, validation_report, result_meta, chart_spec, clarification (jsonb), trace_id, created_at |
| `feedback` | id, message_id, user_id, score (−1/1), comment, created_at; unique (message_id, user_id) |
| `query_log` | id, session_id, sql, status (`ok`/`blocked`/`error`), blocked_level (1–5), duration_ms, row_count, created_at |

- [x] Модели SQLAlchemy 2.1 ([`backend/app/models`](../../backend/app/models)), перечисления как `VARCHAR + CHECK` (ADR-005)
- [x] Миграция Alembic `0001_init`, применяется автоматически при старте контейнера backend
- [x] Тест: `upgrade → check → downgrade → upgrade` на отдельной БД `app_test` (`alembic check` ловит изменения моделей без миграции)
- [x] Таблицы checkpoint'ов LangGraph не создаются вручную: их создаст `PostgresSaver.setup()` в роли 5
- [ ] Шифрование `connection_encrypted` (Fernet, `ENCRYPTION_KEY`) — реализуется в роли 3 вместе с API источников данных

### 2.4 Бенчмарк-БД
- [ ] **Перенесено в роль 7a** ([07_evals.md](07_evals.md)): загрузка нужна только для экспериментов, а выбор подмножества Spider и BIRD делается вместе с набором вопросов

## Definition of Done
- [x] `make seed` создаёт демо-БД за ~8 секунд (требование: < 2 минут), повторный запуск даёт побайтно те же данные
- [x] Все тесты прав `s2d_reader` проходят (`make test-demo-db`: 68 тестов)
- [x] `alembic upgrade head` создаёт схему приложения
- [x] [`docs/demo_db.md`](../demo_db.md): ER-диаграмма, ловушки с примерами вопросов и посчитанными ответами для разных трактовок

## База знаний
- `mcp.md` §2.5 (read-only пользователь БД для SQL-агента)
- `prompting_memory_tools.md` §2.4 (Postgres для структурированных данных)
- `ai_security.md` §4.7 (least privilege)
