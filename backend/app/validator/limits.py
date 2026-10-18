from dataclasses import dataclass

from app.core.config import get_settings


@dataclass(frozen=True)
class Limits:
    """Ограничения проверки и выполнения SQL (значения по умолчанию — из env)."""

    max_rows: int = 1000
    statement_timeout_ms: int = 5000
    max_explain_cost: float = 1_000_000
    # декартово произведение: Nested Loop без условия соединения, где обе стороны больше порога
    cartesian_min_rows: int = 10_000
    max_result_bytes: int = 2_000_000

    @classmethod
    def from_settings(cls) -> "Limits":
        s = get_settings()
        return cls(
            max_rows=s.sql_max_rows,
            statement_timeout_ms=s.sql_statement_timeout_ms,
            max_explain_cost=s.sql_max_explain_cost,
        )
