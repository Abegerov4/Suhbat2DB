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

    # Агент: auto — LangGraph при наличии ключа LLM, иначе заглушка
    agent_mode: Literal["auto", "langgraph", "fake"] = "auto"

    # LLM: модели задаются на узел (strong — генерация SQL и неоднозначность, fast — остальное)
    llm_primary_provider: Literal["anthropic", "openai"] = "openai"
    llm_fallback_provider: Literal["anthropic", "openai"] | None = "anthropic"
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    llm_openai_strong: str = "gpt-4.1"
    llm_openai_fast: str = "gpt-4.1-mini"
    llm_anthropic_strong: str = "claude-sonnet-4-5"
    llm_anthropic_fast: str = "claude-haiku-4-5"
    llm_timeout_s: float = 60
    embedding_model: str = "text-embedding-3-large"

    # Schema linking
    link_top_tables: int = 5
    link_candidates: int = 40
    link_mode: Literal["hybrid", "dense", "sparse"] = "hybrid"
    few_shot_examples: int = 3
    max_clarification_rounds: int = 2

    # Лимиты выполнения SQL
    sql_statement_timeout_ms: int = 5000
    sql_max_rows: int = 1000
    sql_max_explain_cost: float = 1_000_000
    agent_max_corrections: int = 3

    # Трассировка (Langfuse Cloud или локальный); без ключей — отключена
    langfuse_base_url: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    prompts_from_langfuse: bool = False  # True — брать промпты из Langfuse (label production)

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # значения приходят из env
