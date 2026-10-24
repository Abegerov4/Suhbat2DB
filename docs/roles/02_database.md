# Role 2. Database

**Status: completed** (October 2026). The demo database and its "traps" are described in detail in [docs/demo_db.md](../demo_db.md).

**Aim:** a demo database on which ambiguous questions really arise, a safe role for the agent, and the application database schema.
**Depends on:** role 1 (the `app-db` and `target-db` containers).
**Needed for:** Backend, SQL Validator, AI Agent, Evals.

## Tasks

### 2.1 Demo database (`target-db`)

Domain: **sales of a retail chain selling electronics and household goods in Kazakhstan**. It was chosen because all the ambiguity types from the README (§6) arise in it naturally.

| Table | Main columns | Source of ambiguity |
|---|---|---|
| `regions` | id, name, region_type | "Almaty" as the city or together with the region (value) |
| `cities` | id, name, region_id | |
| `customers` | id, full_name, city_id, segment (`b2c`/`b2b`), is_active, registered_at | "customers": all, those who bought, or active ones (scope) |
| `managers` | id, full_name, region_id, hired_at, fired_at | "best managers": by revenue or by number of orders, with or without dismissed ones (scope) |
| `categories`, `products` | id, name, category_id, price, cost, is_discontinued | current price or sale price (schema) |
| `orders` | id, customer_id, manager_id, channel, status, created_at, discount_amount, total_amount | "sales": amount or count (metric); cancelled orders; online orders without a manager |
| `order_items` | order_id, product_id, quantity, unit_price | "sales" as units sold (metric) |
| `payments` | id, order_id, paid_at, amount, method | order date or payment date (temporal); several payments per order |
| `returns` | id, order_id, returned_at, amount, reason | revenue with or without returns |
| `fiscal_calendar` | date, calendar_year/quarter, fiscal_year/quarter | **the fiscal year starts on 1 April** (temporal) |

- [x] DDL in [`demo_db/schema.sql`](../../demo_db/schema.sql) with PKs, FKs, indexes and `CHECK` constraints (including `channel = 'online'` ⇔ `manager_id IS NULL`)
- [x] `COMMENT ON TABLE/COLUMN` in Russian and English for every object (checked by a test)
- [x] Generator [`demo_db/seed.py`](../../demo_db/seed.py) (fixed seed, loading through `COPY`): 30k customers, 200 products, 100k orders over 3 years, growth of ~25% per year, seasonality, ~5% returns. Originally 5k customers were planned, but then there were ~20 orders per customer and 96% of the customers were active, which is not realistic for an electronics store
- [x] Real-world "traps": cancelled orders, `NULL` in `manager_id`, customers without orders, dismissed managers, payment in parts, payment in a different quarter
- [x] Database time zone `Asia/Almaty`: quarters and days are counted in local time

### 2.2 Read-only role
- [x] Role `s2d_reader` ([`demo_db/roles.sql`](../../demo_db/roles.sql)): only `CONNECT`, `USAGE`, `SELECT`. The privileges of `PUBLIC` on the database (including `TEMP`) and on the `public` schema are revoked
- [x] Session limits: `default_transaction_read_only`, `statement_timeout = 5s`, `idle_in_transaction_session_timeout`, `CONNECTION LIMIT 20`
- [x] Tests: 17 dangerous commands × 2 modes (`default_transaction_read_only` can be turned off from the session, so the guarantee comes from the privileges, and this is tested separately), `GRANT` without effect, `pg_sleep` timeout, no privileges on the role

### 2.3 Application database (`app-db`)

| Table | Columns |
|---|---|
| `users` | id (uuid), email (unique), password_hash, role (`admin`/`analyst`), created_at |
| `datasources` | id, owner_id → users, name, dialect, connection_encrypted, status, error, schema_snapshot (jsonb), indexed_at, created_at |
| `chat_sessions` | id (= LangGraph `thread_id`), user_id, datasource_id, title, created_at, updated_at |
| `messages` | id, session_id, role, content, sql, validation_report, result_meta, chart_spec, clarification (jsonb), trace_id, created_at |
| `feedback` | id, message_id, user_id, score (−1/1), comment, created_at; unique (message_id, user_id) |
| `query_log` | id, session_id, sql, status (`ok`/`blocked`/`error`), blocked_level (1–5), duration_ms, row_count, created_at |

- [x] SQLAlchemy 2.1 models ([`backend/app/models`](../../backend/app/models)), enumerations as `VARCHAR + CHECK` (ADR-005)
- [x] Alembic migration `0001_init`, applied automatically when the backend container starts
- [x] Test: `upgrade → check → downgrade → upgrade` on a separate `app_test` database (`alembic check` catches model changes without a migration)
- [x] LangGraph checkpoint tables are not created by hand: `PostgresSaver.setup()` creates them in role 5
- [ ] Encryption of `connection_encrypted` (Fernet, `ENCRYPTION_KEY`), implemented in role 3 together with the data source API

### 2.4 Benchmark databases
- [ ] **Moved to role 7a** ([07_evals.md](07_evals.md)): loading is needed only for the experiments, and the Spider and BIRD subsets are chosen together with the question set

## Definition of Done
- [x] `make seed` creates the demo database in ~8 seconds (requirement: < 2 minutes), and a repeated run gives byte-identical data
- [x] All `s2d_reader` privilege tests pass (`make test-demo-db`: 68 tests)
- [x] `alembic upgrade head` creates the application schema
- [x] [`docs/demo_db.md`](../demo_db.md): ER diagram, traps with sample questions and computed answers for different interpretations

## Knowledge base
- `mcp.md` §2.5 (a read-only database user for an SQL agent)
- `prompting_memory_tools.md` §2.4 (Postgres for structured data)
- `ai_security.md` §4.7 (least privilege)
