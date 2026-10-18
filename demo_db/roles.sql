-- Права для роли агента (уровень 5 валидатора, defense in depth).
-- Выполняется после загрузки данных. Плейсхолдеры {reader} и {database}
-- подставляет seed.py через psycopg.sql (экранирование идентификаторов).
-- Пароль роли задаётся отдельно (ALTER ROLE ... PASSWORD) в seed.py.

-- Никто, кроме явно разрешённых ролей, не подключается и не создаёт временные таблицы
REVOKE ALL ON DATABASE {database} FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

-- Агенту: только подключение, видимость схемы и SELECT
GRANT CONNECT ON DATABASE {database} TO {reader};
GRANT USAGE ON SCHEMA public TO {reader};
GRANT SELECT ON ALL TABLES IN SCHEMA public TO {reader};

-- Ограничения сессии. default_transaction_read_only — дополнительный слой:
-- пользователь может отключить его через SET, поэтому гарантию дают
-- права выше (у роли нет INSERT/UPDATE/DELETE/CREATE/TEMP).
ALTER ROLE {reader} SET default_transaction_read_only = on;
ALTER ROLE {reader} SET statement_timeout = '5s';
ALTER ROLE {reader} SET idle_in_transaction_session_timeout = '10s';
ALTER ROLE {reader} SET search_path = public;
ALTER ROLE {reader} CONNECTION LIMIT 20;
