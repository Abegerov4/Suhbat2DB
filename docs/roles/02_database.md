# Роль 2. Database

**Цель:** демонстрационная БД, на которой реально возникают неоднозначные вопросы, безопасная роль для агента и схема БД приложения.
**Зависит от:** роль 1 (контейнеры `app-db` и `target-db`).
**Нужно для:** Backend, SQL Validator, AI Agent, Evals.

## Задачи

### 2.1 Демо-БД (`target-db`)

Домен: **продажи розничной сети в Казахстане**. Его выбрали потому, что в нём естественно возникают все типы неоднозначности из README (§6).

| Таблица | Ключевые столбцы | Источник неоднозначности |
|---|---|---|
| `regions` | id, name | «Алматы» как город или как область (value) |
| `cities` | id, name, region_id | |
| `customers` | id, full_name, city_id, segment (`b2c`/`b2b`), registered_at | «клиенты»: все или только активные (scope) |
| `managers` | id, full_name, region_id, hired_at | «лучшие менеджеры»: по чему (scope) |
| `categories`, `products` | id, name, category_id, price, cost | |
| `orders` | id, customer_id, manager_id, status, created_at, total_amount | «продажи»: сумма или количество заказов (metric); `status` влияет на выбор между «оформленные» и «оплаченные» |
| `order_items` | order_id, product_id, quantity, unit_price | «продажи» как проданные единицы (metric) |
| `payments` | id, order_id, paid_at, amount, method | дата «продажи»: дата заказа или дата оплаты (temporal) |
| `returns` | id, order_id, returned_at, amount | «чистая выручка» с учётом возвратов или без |
| `fiscal_calendar` | date, fiscal_year, fiscal_quarter | **финансовый год начинается 1 апреля**, поэтому квартал может быть календарным или финансовым (temporal) |

- [ ] DDL в `demo_db/schema.sql` с PK, FK, индексами и `CHECK`
- [ ] `COMMENT ON TABLE/COLUMN` на русском и английском для каждого объекта: из комментариев строятся описания для schema linking
- [ ] Генератор данных `demo_db/seed.py` (Faker с `ru_RU`, фиксированный `seed` для воспроизводимости): ~5k клиентов, ~200 товаров, ~100k заказов за 3 года, сезонность, ~5% возвратов
- [ ] Намеренные «ловушки» реального мира: заказы в статусе `cancelled`, `NULL` в `manager_id`, клиенты без заказов

### 2.2 Роль только для чтения
```sql
CREATE ROLE s2d_reader LOGIN PASSWORD '...' NOSUPERUSER NOCREATEDB NOCREATEROLE;
GRANT CONNECT ON DATABASE demo TO s2d_reader;
GRANT USAGE ON SCHEMA public TO s2d_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO s2d_reader;
ALTER ROLE s2d_reader SET default_transaction_read_only = on;
ALTER ROLE s2d_reader SET statement_timeout = '5s';
REVOKE ALL ON SCHEMA public FROM PUBLIC;
```
- [ ] Тест: под `s2d_reader` не проходят `INSERT`, `UPDATE`, `DELETE`, `DROP`, `CREATE TEMP TABLE`, `COPY ... TO`, `pg_read_file`, `pg_sleep(10)` (срабатывает timeout)
- [ ] Эта роль реализует уровень 5 валидатора (defense in depth): даже ошибка в коде не даст изменить данные

### 2.3 БД приложения (`app-db`)

| Таблица | Столбцы |
|---|---|
| `users` | id (uuid), email (unique), password_hash, role (`admin`/`analyst`), created_at |
| `datasources` | id, owner_id → users, name, dialect, connection_encrypted, status, error, schema_snapshot (jsonb), indexed_at |
| `chat_sessions` | id (= LangGraph `thread_id`), user_id, datasource_id, title, created_at |
| `messages` | id, session_id, role, content, sql, validation_report (jsonb), result_meta (jsonb), chart_spec (jsonb), clarification (jsonb), trace_id, created_at |
| `feedback` | id, message_id, user_id, score (−1/1), comment, created_at |
| `query_log` | id, session_id, sql, status (`ok`/`blocked`/`error`), blocked_level, duration_ms, row_count, created_at |

- [ ] SQLAlchemy 2.0 модели и миграции **Alembic** (первая миграция `0001_init`)
- [ ] Таблицы checkpoint'ов LangGraph не создаются вручную: их создаёт `PostgresSaver.setup()` в роли 5
- [ ] `connection_encrypted` шифруется Fernet, ключ хранится в `ENCRYPTION_KEY` в env

### 2.4 Бенчмарк-БД (для роли 7)
- [ ] Скрипт загрузки выбранных БД **Spider** и **BIRD** в отдельные базы `target-db` (Spider и BIRD распространяются в SQLite, нужна конвертация в PostgreSQL через `pgloader` или sqlglot-транспиляцию DDL с последующей проверкой)
- [ ] Для каждой загруженной БД свой `s2d_reader` с теми же ограничениями

## Definition of Done
- `make seed` создаёт демо-БД с данными за < 2 минут, повторный запуск идемпотентен
- Все тесты прав `s2d_reader` проходят (pytest)
- `alembic upgrade head` создаёт схему приложения
- В `docs/demo_db.md` есть ER-диаграмма (Mermaid) и список «ловушек» с примерами неоднозначных вопросов к ним

## База знаний
- `mcp.md` §2.5 (read-only пользователь БД для SQL-агента)
- `prompting_memory_tools.md` §2.4 (Postgres для структурированных данных)
- `ai_security.md` §4.7 (least privilege)
