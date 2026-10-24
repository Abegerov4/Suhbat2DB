# Role 4. SQL Validator

**Status: completed** (October 2026). The rules, their reasons and the results are in [docs/validator.md](../validator.md) (the basis for chapter 2 of the diploma).

**Aim:** a deterministic `app.validator` module that guarantees that only a safe, syntactically correct `SELECT` consistent with the schema reaches execution. This is the core of the research part of the diploma, so the module is covered by tests more thoroughly than the others.
**Depends on:** role 2 (`s2d_reader`), role 3 (`SchemaSnapshot`, connection pools).
**Needed for:** AI Agent (the `validate_sql` and `execute` nodes), Evals (the unsafe block rate metric).

Interface: [`CONTRACTS.md` §3](../CONTRACTS.md#3-sql-validator).

## Tasks

### 4.1 Level 1: syntax
- [x] `sqlglot.parse(sql, read="postgres")`, an error with the line number, position and fragment
- [x] Exactly one statement, otherwise `fatal`. A bare `SELECT` without columns is rejected
- [x] A construct that cannot be parsed is not executed (allowlist by the parser)

### 4.2 Level 2: read-only policy (`fatal`)
- [x] The root is only `SELECT`/`UNION`/`INTERSECT`/`EXCEPT`. sqlglot parses `LISTEN ch` and `TABLE orders` as an expression with an alias, so the root is checked explicitly
- [x] 28 forbidden node types anywhere in the tree, including data-modifying CTEs, `SELECT INTO`, `FOR UPDATE/SHARE` and utility `Command` nodes
- [x] 36 prefixes of dangerous functions: delay, server files, `dblink`, session control, `query_to_xml`, sequences, transactions, locks, replication
- [x] System catalogs: `pg_catalog`, `information_schema`, `pg_toast`, unqualified `pg_*`
- [x] Letter case, quotes and comments do not help: the check works on the AST

### 4.3 Level 3: schema check
- [x] Existence of tables (taking `search_path` into account) and columns (`sqlglot.optimizer.qualify`), unambiguous references
- [x] Hints: similar table and column names, columns with the same name in other tables, a note about ambiguity
- [x] Unquoted identifiers are lowercased, as in PostgreSQL. Without this `SELECT … FROM ORDERS` was falsely blocked; a property-based test found it
- [x] A string compared with a date must be a date. Originally a warning was planned, but PostgreSQL rejects such a query anyway, so it is an error with a hint (`date_trunc(…)`)
- [x] Normalisation: comments are removed, outer `LIMIT` ≤ `max_rows + 1`

### 4.4 Level 4: EXPLAIN
- [x] `EXPLAIN (FORMAT JSON)` without `ANALYZE`, in a read-only transaction with a timeout
- [x] Cost threshold `SQL_MAX_EXPLAIN_COST`
- [x] Cartesian product detector (a `Nested Loop` without a join condition, both sides > 10,000 rows). A self-join on a key does not trigger it (test)
- [x] Planner errors → `passed=False` with the PostgreSQL text
- [ ] ~~`SQL_MAX_EXPLAIN_ROWS`~~ not needed: the result is limited by `LIMIT`, and large intermediate results are reflected in the cost

### 4.5 Level 5: isolated execution
- [x] `BEGIN READ ONLY` → `SET LOCAL statement_timeout`, `idle_in_transaction_session_timeout` → a cursor for `max_rows + 1` rows → `ROLLBACK`
- [x] JSON serialisation: `numeric` → number (for charts), dates → ISO, `bytea`, `uuid`, arrays, `json`
- [x] Response size limit of 2 MB → `truncated`
- [x] `ExecutionError` with a level 5 `ValidationLevelResult`: timeout, execution errors

### 4.6 Tests
- [x] **88 attacks** in [`evals/datasets/unsafe/sql_attacks.jsonl`](../../evals/datasets/unsafe/sql_attacks.jsonl), 9 categories (DDL, DML, several statements, data-modifying CTEs, `INTO`/locks, utility commands, dangerous functions, system catalogs, obfuscation), 100% blocked at levels 1–2
- [x] **42 harmless queries** in [`sql_benign.jsonl`](../../evals/datasets/unsafe/sql_benign.jsonl), 0 false blocks. All of them pass levels 1–5 on the real demo database
- [x] Level 3 tests that check the hints
- [x] Integration tests of levels 4–5 on a test target database (20,000 rows): Cartesian product, cost threshold, planner error, timeout, truncation by rows and bytes; `DELETE` as a superuser does not pass because of the read-only transaction
- [x] Property-based tests (hypothesis, 300 examples): dangerous fragments anywhere in an allowed query
- [x] The datasets are in `evals/datasets/unsafe/` and are shared with role 7

## Definition of Done
- [x] 100% of the attack tests are blocked, 0 false blocks on the harmless set
- [x] Coverage of `app/validator` ≥ 90%: **96%** of lines and branches
- [x] Levels 1–3 < 20 ms: median **0.58 ms**, p95 1.46 ms
- [x] [`docs/validator.md`](../validator.md): all rules with their reasons, and the results

## Knowledge base
- `ai_engineering.md` §2.4 and §6 (a strict SQL format is checked by a code critic, not by an LLM)
- `ai_security.md` §4.2 (levels 3 and 5: output validation and control of actions), §2.1 (the prompt is not a barrier; the code provides the protection)
- `mcp.md` §7.1 (rules of the Postgres skill: "never DELETE without WHERE", "on an error, get_schema first")
