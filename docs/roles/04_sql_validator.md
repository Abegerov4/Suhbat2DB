# Роль 4. SQL Validator

**Цель:** детерминированный модуль `app.validator`, который гарантирует, что до выполнения доходит только безопасный, синтаксически корректный и согласованный со схемой `SELECT`. Это ядро научной части диплома, поэтому модуль покрывается тестами плотнее остальных.
**Зависит от:** роль 2 (`s2d_reader`), роль 3 (`SchemaSnapshot`, пулы соединений).
**Нужно для:** AI Agent (узлы `validate_sql`, `execute`), Evals (метрика unsafe block rate).

Интерфейс зафиксирован в [`CONTRACTS.md` §3](../CONTRACTS.md#3-валидатор-sql).

## Задачи

### 4.1 Уровень 1 — синтаксис
- [ ] `sqlglot.parse(sql, read="postgres")`, ошибка `ParseError` → `passed=False`, `message` с позицией ошибки
- [ ] Ровно одно выражение: `SELECT 1; DROP TABLE x` → `fatal=True`
- [ ] Удаление комментариев и нормализация перед следующими уровнями

### 4.2 Уровень 2 — политика read-only (`fatal=True` при нарушении)
- [ ] Корень AST: только `exp.Select`, `exp.Union`/`Intersect`/`Except`, а также `exp.With`, внутри которого только они
- [ ] Обход **всего** дерева (в том числе подзапросов и CTE) на запрещённые узлы: `Insert`, `Update`, `Delete`, `Drop`, `Create`, `Alter`, `TruncateTable`, `Command` (неразобранные команды: `COPY`, `GRANT`, `SET`, `VACUUM`…), `Into` (`SELECT … INTO`), `Lock` / `FOR UPDATE`
- [ ] Data-modifying CTE в PostgreSQL (`WITH d AS (DELETE … RETURNING *) SELECT …`) блокируются
- [ ] Denylist функций: `pg_sleep*`, `pg_read_file`, `pg_read_binary_file`, `pg_ls_dir`, `lo_*`, `dblink*`, `pg_terminate_backend`, `pg_cancel_backend`, `set_config`, `current_setting`, `pg_reload_conf`, `query_to_xml`, `txid_*`
- [ ] Denylist схем: `pg_catalog`, `information_schema`, `pg_toast`. Allowlist таблиц берётся из `SchemaSnapshot`
- [ ] Обход через регистр, кавычки и пробелы (`"DeLeTe"`, `pg_catalog."pg_user"`) нейтрализуется самим AST. Тесты это подтверждают

### 4.3 Уровень 3 — сверка со схемой
- [ ] `sqlglot.optimizer.qualify.qualify(expr, schema=MappingSchema(...), dialect="postgres")` → неизвестные таблицы и столбцы, неоднозначные ссылки
- [ ] **Подсказка для самокоррекции:** для неизвестного идентификатора ищется ближайший существующий (`difflib.get_close_matches` по именам и по комментариям): `hint="столбца sales.amount нет; возможно, orders.total_amount"`
- [ ] Проверка типов в простых сравнениях (`date_column = 'abc'`) на уровне предупреждения, без блокировки (`passed=True`, `message`)

### 4.4 Уровень 4 — EXPLAIN
- [ ] `EXPLAIN (FORMAT JSON) <sql>` под `s2d_reader`, **без `ANALYZE`** (`ANALYZE` выполняет запрос)
- [ ] Пороги из env: `SQL_MAX_EXPLAIN_COST`, `SQL_MAX_EXPLAIN_ROWS`
- [ ] Детектор декартова произведения: `Nested Loop` без `Join Filter`/`Index Cond` при оценке строк обеих сторон > 10k
- [ ] Ошибки планировщика (например, несовместимые типы) → `passed=False` с текстом ошибки СУБД в `message`

### 4.5 Уровень 5 — изолированное выполнение
- [ ] Принудительный `LIMIT`: если внешний `LIMIT` отсутствует или больше `SQL_MAX_ROWS`, SQL переписывается через AST (`LIMIT SQL_MAX_ROWS + 1`, по лишней строке определяется `truncated=True`)
- [ ] Выполнение в транзакции:
  ```sql
  BEGIN TRANSACTION READ ONLY;
  SET LOCAL statement_timeout = :timeout;
  SET LOCAL idle_in_transaction_session_timeout = :timeout;
  <sql>;
  ROLLBACK;
  ```
- [ ] Сериализация типов (`Decimal`, `date`, `timestamp`, `uuid`, `interval`) в JSON
- [ ] Ограничение размера ответа (например, 2 МБ), иначе `truncated=True`

### 4.6 Тесты (главный артефакт роли)
- [ ] `tests/validator/test_policy.py`: **не менее 60 атакующих запросов**, каждый должен давать `fatal=True`. Категории: DDL, DML, data-modifying CTE, `SELECT INTO`, множественные выражения, опасные функции, системные каталоги, обход регистром и кавычками, комментарии `/* */` и `--` внутри
- [ ] **Не менее 30 безобидных запросов**, которые не должны блокироваться: оконные функции, CTE, `UNION`, `CASE`, подзапросы, столбец с именем `deleted_at`, строковый литерал `'DROP'`
- [ ] Тесты уровня 3 с проверкой подсказок
- [ ] Интеграционные тесты уровней 4–5 на демо-БД (timeout, truncated, тяжёлый `CROSS JOIN`)
- [ ] Property-based тест (`hypothesis`): случайные комбинации запрещённых узлов внутри допустимого `SELECT` всегда блокируются
- [ ] Те же наборы экспортируются в `evals/datasets/unsafe/` для роли 7

## Definition of Done
- 100% атакующих тестов заблокированы, 0 ложных блокировок на безобидном наборе
- Покрытие `app/validator` ≥ 90% (строки и ветви)
- Время уровней 1–3 < 20 мс на типичный запрос (замер в тесте)
- В `docs/validator.md` описаны все правила политики с обоснованием (этот текст войдёт в главу 2 диплома)

## База знаний
- `ai_engineering.md` §2.4 и §6 (строгий формат SQL проверяет критик-код, а не LLM)
- `ai_security.md` §4.2 (уровни 3 и 5: валидация вывода и контроль действий), §2.1 (промпт — не барьер, защиту обеспечивает код)
- `mcp.md` §7.1 (правила Postgres-skill: «никогда DELETE без WHERE», «при ошибке сначала get_schema»)
