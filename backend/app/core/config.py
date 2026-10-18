from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация приложения из переменных окружения.

    Поля без значения по умолчанию обязательны: если переменной нет,
    приложение падает при старте, а не на первом запросе.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Приложение
    app_env: Literal["dev", "test", "prod"] = "dev"
    app_database_url: str
    qdrant_url: str
    jwt_secret: SecretStr
    jwt_ttl_minutes: int = 24 * 60
    # ключ Fernet для шифрования строк подключения к пользовательским БД
    app_encryption_key: SecretStr
    cors_origins: list[str] = ["http://localhost:3000"]

    # Первый администратор создаётся при старте, если его ещё нет
    admin_email: str | None = None
    admin_password: SecretStr | None = None

    # Демо-БД регистрируется как источник данных при старте (если задано)
    demo_datasource_url: SecretStr | None = None
    demo_datasource_name: str = "Демо: продажи в Казахстане"

    # LLM (обязательными станут в роли 5)
    llm_primary_provider: Literal["anthropic", "openai"] = "anthropic"
    llm_fallback_provider: Literal["anthropic", "openai"] | None = "openai"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    # Лимиты выполнения SQL
    sql_statement_timeout_ms: int = 5000
    sql_max_rows: int = 1000
    sql_max_explain_cost: float = 1_000_000
    agent_max_corrections: int = 3

    # Трассировка
    langfuse_host: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()  # значения приходят из env
