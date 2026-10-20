import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALS = ROOT / "evals"
DATASETS = EVALS / "datasets"
CONFIGS = EVALS / "configs"
REPORTS = EVALS / "reports"
DATA = EVALS / "data"  # не в git: скачанные бенчмарки и кэш LLM
SPIDER = DATA / "spider" / "spider_data"
BIRD = DATA / "bird" / "dev_20240627"


def target_url(database: str, *, admin: bool = False) -> str:
    """URL целевой БД (контейнер target-db) из переменных .env."""
    env = os.environ
    user = env["TARGET_DB_ADMIN_USER" if admin else "TARGET_DB_READER_USER"]
    password = env["TARGET_DB_ADMIN_PASSWORD" if admin else "TARGET_DB_READER_PASSWORD"]
    host = env.get("TARGET_DB_HOST", "localhost")
    port = env.get("TARGET_DB_PORT", "5443")
    return f"postgresql://{user}:{password}@{host}:{port}/{database}"


def local_env_defaults() -> None:
    """Адреса сервисов для запуска evals с хоста (в контейнере их задаёт docker compose)."""
    env = os.environ
    env.setdefault("QDRANT_URL", "http://localhost:6333")
    if "APP_DATABASE_URL" not in env and "APP_DB_PASSWORD" in env:
        env["APP_DATABASE_URL"] = (
            f"postgresql://{env.get('APP_DB_USER', 'app')}:{env['APP_DB_PASSWORD']}"
            f"@localhost:{env.get('APP_DB_PORT', '5442')}/{env.get('APP_DB_NAME', 'app')}"
        )
