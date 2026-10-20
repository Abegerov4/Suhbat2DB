"""Оценка агента (docs/roles/07_evals.md).

Код живёт в backend/, потому что использует граф и валидатор приложения; наборы данных,
отчёты и скачанные бенчмарки — в корневой папке evals/.

    cd backend && uv run python -m evals.run --suite spider_subset --config agent
"""
