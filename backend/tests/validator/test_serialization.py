import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.validator import Limits
from app.validator.executor import to_json


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (True, True),
        (42, 42),
        ("Алматы", "Алматы"),
        (1.5, 1.5),
        (float("nan"), "nan"),
        (float("inf"), "inf"),
        (Decimal("1489214330.00"), 1489214330),
        (Decimal("12.34"), 12.34),
        (date(2026, 7, 1), "2026-07-01"),
        (
            datetime(2026, 7, 1, 10, 0, tzinfo=timezone(timedelta(hours=5))),
            "2026-07-01T10:00:00+05:00",
        ),
        (time(9, 30), "09:30:00"),
        (timedelta(days=2, hours=3), "2 days, 3:00:00"),
        (uuid.UUID(int=1), "00000000-0000-0000-0000-000000000001"),
        (b"\x00\x01", "<binary 2 bytes>"),
        ([Decimal("1"), date(2026, 1, 1)], [1, "2026-01-01"]),
        ({"a": Decimal("2.5")}, {"a": 2.5}),
        (object, str(object)),
    ],
)
def test_to_json(value: object, expected: object) -> None:
    assert to_json(value) == expected


def test_limits_from_settings() -> None:
    limits = Limits.from_settings()
    settings = get_settings()
    assert limits.max_rows == settings.sql_max_rows
    assert limits.statement_timeout_ms == settings.sql_statement_timeout_ms
