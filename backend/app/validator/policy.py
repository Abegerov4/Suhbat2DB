"""Уровень 2: политика «только чтение». Любое нарушение фатально — самокоррекции нет.

Проверка идёт по AST, а не по тексту: регистр, кавычки, пробелы и комментарии
не помогают обойти правила. Обходится всё дерево, включая подзапросы и CTE.
"""

from sqlglot import exp

from app.schemas.agent import ValidationLevelResult

ALLOWED_ROOTS: tuple[type[exp.Expr], ...] = (
    exp.Select,
    exp.Union,
    exp.Intersect,
    exp.Except,
)

# Узлы, которые не могут встречаться нигде в дереве запроса
FORBIDDEN_NODES: dict[type[exp.Expr], str] = {
    exp.Insert: "INSERT",
    exp.Update: "UPDATE",
    exp.Delete: "DELETE",
    exp.Merge: "MERGE",
    exp.Drop: "DROP",
    exp.Create: "CREATE",
    exp.Alter: "ALTER",
    exp.TruncateTable: "TRUNCATE",
    exp.Copy: "COPY",
    exp.Into: "SELECT … INTO (создаёт таблицу)",
    exp.Lock: "FOR UPDATE / FOR SHARE (блокировка строк)",
    exp.Set: "SET (изменение настроек сессии)",
    exp.Grant: "GRANT",
    exp.Revoke: "REVOKE",
    exp.Transaction: "управление транзакциями",
    exp.Commit: "COMMIT",
    exp.Rollback: "ROLLBACK",
    exp.Use: "USE",
    exp.Pragma: "PRAGMA",
    exp.Analyze: "ANALYZE",
    exp.LoadData: "LOAD DATA",
    exp.Describe: "DESCRIBE",
    exp.Cache: "CACHE",
    exp.Uncache: "UNCACHE",
    exp.Refresh: "REFRESH",
    exp.Kill: "KILL",
    exp.Comment: "COMMENT",
    exp.Command: "служебная команда (VACUUM, DO, CALL, SHOW, PREPARE, …)",
}

# Функции с побочными эффектами, доступом к файлам/сети/сессии или задержкой выполнения.
# Значение — префикс имени (сравнение без учёта регистра).
FORBIDDEN_FUNCTION_PREFIXES: dict[str, str] = {
    "pg_sleep": "задержка выполнения",
    "pg_read_file": "чтение файлов сервера",
    "pg_read_binary_file": "чтение файлов сервера",
    "pg_ls_": "просмотр каталогов сервера",
    "pg_stat_file": "доступ к файлам сервера",
    "pg_file_": "запись файлов сервера",
    "lo_": "large objects (импорт и экспорт файлов)",
    "dblink": "подключение к другим БД",
    "pg_terminate_backend": "завершение чужих сессий",
    "pg_cancel_backend": "отмена чужих запросов",
    "pg_reload_conf": "перезагрузка конфигурации",
    "pg_rotate_logfile": "управление логами сервера",
    "set_config": "изменение настроек сессии",
    "current_setting": "чтение настроек сервера",
    "query_to_xml": "выполнение произвольного SQL из строки",
    "table_to_xml": "выгрузка таблиц в обход политики",
    "database_to_xml": "выгрузка базы",
    "schema_to_xml": "выгрузка схемы",
    "cursor_to_xml": "работа с курсорами",
    "nextval": "изменение последовательности",
    "setval": "изменение последовательности",
    "txid_": "управление транзакциями",
    "pg_current_xact_id": "выделение идентификатора транзакции",
    "pg_advisory_": "блокировки",
    "pg_try_advisory_": "блокировки",
    "pg_notify": "отправка уведомлений",
    "pg_logical_": "логическая репликация",
    "pg_replication_": "управление репликацией",
    "pg_create_": "создание слотов и точек восстановления",
    "pg_drop_replication_slot": "управление репликацией",
    "pg_switch_wal": "управление WAL",
    "pg_stat_reset": "сброс статистики",
    "pg_promote": "управление репликой",
    "pg_backup_": "резервное копирование",
    "pg_log_backend_memory_contexts": "запись в лог сервера",
    "pg_import_system_collations": "изменение каталога",
}

SYSTEM_SCHEMAS = {"pg_catalog", "information_schema", "pg_toast"}


def function_name(func: exp.Func) -> str:
    if isinstance(func, exp.Anonymous):
        return str(func.name).lower()
    return func.sql_name().lower()


def violations(expression: exp.Expr) -> list[str]:
    found: list[str] = []
    if not isinstance(expression, ALLOWED_ROOTS):
        found.append("разрешены только запросы на чтение (SELECT)")

    for node in expression.walk():
        for node_type, label in FORBIDDEN_NODES.items():
            if isinstance(node, node_type):
                found.append(f"запрещённая операция: {label}")
        if isinstance(node, exp.Func):
            name = function_name(node)
            for prefix, reason in FORBIDDEN_FUNCTION_PREFIXES.items():
                if name.startswith(prefix):
                    found.append(f"запрещённая функция {name}() — {reason}")
                    break
        if isinstance(node, exp.Table) and isinstance(node.this, exp.Identifier):
            schema = node.db.lower()
            table = node.name.lower()
            if schema in SYSTEM_SCHEMAS or (not schema and table.startswith("pg_")):
                found.append(f"обращение к системному каталогу: {node.sql(dialect='postgres')}")

    return list(dict.fromkeys(found))  # без повторов, в порядке обнаружения


def check_policy(expression: exp.Expr) -> ValidationLevelResult:
    found = violations(expression)
    if found:
        return ValidationLevelResult(
            level=2,
            name="readonly_policy",
            passed=False,
            message="Запрос нарушает политику «только чтение»: " + "; ".join(found),
            fatal=True,
        )
    return ValidationLevelResult(
        level=2, name="readonly_policy", passed=True, message="Только чтение данных"
    )
