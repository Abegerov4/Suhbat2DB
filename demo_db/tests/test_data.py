"""Целостность и «ловушки» демо-БД.

Ловушки — это намеренные особенности данных, из-за которых возникает неоднозначность
вопросов (docs/demo_db.md). Если ловушка пропадёт, часть набора ambiguous_ru станет
однозначной, поэтому их наличие проверяется тестами.
"""

from typing import Any

import psycopg
import pytest


def scalar(conn: psycopg.Connection, query: str) -> Any:
    row = conn.execute(query).fetchone()
    assert row is not None
    return row[0]


# --- Целостность ---------------------------------------------------------------------------

INVARIANTS = {
    "total_equals_items_minus_discount": """
        SELECT count(*) FROM orders o
        JOIN (SELECT order_id, sum(quantity * unit_price) s FROM order_items GROUP BY 1) i
          ON i.order_id = o.id
        WHERE o.total_amount <> i.s - o.discount_amount
    """,
    "every_order_has_items": """
        SELECT count(*) FROM orders o
        WHERE NOT EXISTS (SELECT 1 FROM order_items i WHERE i.order_id = o.id)
    """,
    "payments_sum_to_total": """
        SELECT count(*) FROM orders o
        JOIN (SELECT order_id, sum(amount) s FROM payments GROUP BY 1) p ON p.order_id = o.id
        WHERE p.s <> o.total_amount
    """,
    "no_payments_for_cancelled_or_new": """
        SELECT count(*) FROM payments p JOIN orders o ON o.id = p.order_id
        WHERE o.status IN ('cancelled', 'new')
    """,
    "paid_orders_have_payments": """
        SELECT count(*) FROM orders o
        WHERE o.status IN ('paid', 'shipped', 'delivered')
          AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.order_id = o.id)
    """,
    "payment_after_order": """
        SELECT count(*) FROM payments p JOIN orders o ON o.id = p.order_id
        WHERE p.paid_at < o.created_at
    """,
    "returns_only_for_delivered": """
        SELECT count(*) FROM returns r JOIN orders o ON o.id = r.order_id
        WHERE o.status <> 'delivered' OR r.returned_at <= o.created_at
           OR r.amount > o.total_amount
    """,
    "order_after_registration": """
        SELECT count(*) FROM orders o JOIN customers c ON c.id = o.customer_id
        WHERE o.created_at < c.registered_at
    """,
    "manager_active_and_in_customer_region": """
        SELECT count(*) FROM orders o
        JOIN managers m ON m.id = o.manager_id
        JOIN customers c ON c.id = o.customer_id
        JOIN cities ci ON ci.id = c.city_id
        WHERE o.created_at::date < m.hired_at
           OR o.created_at::date >= m.fired_at
           OR m.region_id <> ci.region_id
    """,
    "discontinued_products_not_sold_now": """
        SELECT count(*) FROM order_items i
        JOIN orders o ON o.id = i.order_id
        JOIN products p ON p.id = i.product_id
        WHERE p.is_discontinued AND o.created_at > now() - interval '1 day'
          AND o.created_at::date >= '2026-10-18'
    """,
    "is_active_matches_last_order": """
        SELECT count(*) FROM customers c
        LEFT JOIN (SELECT customer_id, max(created_at) last FROM orders GROUP BY 1) o
          ON o.customer_id = c.id
        WHERE c.is_active <> coalesce(o.last >= '2026-10-18 23:59+05'::timestamptz
                                      - interval '365 days', false)
    """,
}


@pytest.mark.parametrize("query", INVARIANTS.values(), ids=INVARIANTS.keys())
def test_invariant(admin: psycopg.Connection, query: str) -> None:
    assert scalar(admin, query) == 0


def test_every_table_and_column_has_comment(admin: psycopg.Connection) -> None:
    missing = admin.execute("""
        SELECT c.relname || coalesce('.' || a.attname, '')
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = 'public'
        LEFT JOIN pg_attribute a ON a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped
        WHERE c.relkind = 'r'
          AND obj_description(c.oid, 'pg_class') IS NULL
           OR (a.attnum IS NOT NULL AND col_description(c.oid, a.attnum) IS NULL
               AND c.relkind = 'r' AND n.nspname = 'public')
    """).fetchall()
    assert missing == []


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        ("2026-03-31", (2026, 1, 2025, 4)),
        ("2026-04-01", (2026, 2, 2026, 1)),
        ("2026-09-30", (2026, 3, 2026, 2)),
        ("2026-12-31", (2026, 4, 2026, 3)),
    ],
)
def test_fiscal_calendar(admin: psycopg.Connection, day: str, expected: tuple[int, ...]) -> None:
    row = admin.execute(
        "SELECT calendar_year, calendar_quarter, fiscal_year, fiscal_quarter "
        "FROM fiscal_calendar WHERE date = %s",
        (day,),
    ).fetchone()
    assert row == expected


# --- Ловушки неоднозначности ----------------------------------------------------------------

TRAPS = {
    # «продажи»: выручка, число заказов или проданные единицы дают разные рейтинги
    "cancelled_orders_exist": "SELECT count(*) FROM orders WHERE status = 'cancelled'",
    # «продажи за квартал»: по дате заказа или по дате оплаты
    "payment_in_other_quarter": """
        SELECT count(*) FROM payments p JOIN orders o ON o.id = p.order_id
        WHERE date_trunc('quarter', p.paid_at) <> date_trunc('quarter', o.created_at)
    """,
    # платежей больше, чем заказов: JOIN orders–payments раздувает сумму
    "orders_with_several_payments": """
        SELECT count(*) FROM (SELECT order_id FROM payments GROUP BY 1 HAVING count(*) > 1) t
    """,
    # «выручка»: с вычетом возвратов или без
    "returns_exist": "SELECT count(*) FROM returns",
    # «продажи менеджеров»: онлайн-заказы без менеджера
    "orders_without_manager": "SELECT count(*) FROM orders WHERE manager_id IS NULL",
    # «клиенты»: зарегистрированные, покупавшие или активные
    "customers_without_orders": """
        SELECT count(*) FROM customers c
        WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)
    """,
    "inactive_customers_with_orders": """
        SELECT count(*) FROM customers c
        WHERE NOT c.is_active AND EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id)
    """,
    # «менеджеры»: только работающие или все, включая уволенных
    "fired_managers": "SELECT count(*) FROM managers WHERE fired_at IS NOT NULL",
    # «цена»: текущая цена товара или цена на момент продажи
    "price_differs_from_sale_price": """
        SELECT count(*) FROM order_items i JOIN products p ON p.id = i.product_id
        WHERE i.unit_price <> p.price
    """,
    # «квартал»: календарный и финансовый не совпадают
    "fiscal_differs_from_calendar": """
        SELECT count(*) FROM fiscal_calendar WHERE fiscal_quarter <> calendar_quarter
    """,
}


@pytest.mark.parametrize("query", TRAPS.values(), ids=TRAPS.keys())
def test_trap_present(admin: psycopg.Connection, query: str) -> None:
    assert scalar(admin, query) > 0


def test_almaty_is_ambiguous(admin: psycopg.Connection) -> None:
    """«Алматы» — и регион-город, и часть названия «Алматинская область»."""
    names = [r[0] for r in admin.execute("SELECT name FROM regions WHERE name ILIKE 'алмат%'")]
    assert sorted(names) == ["Алматинская область", "Алматы"]


def test_seasonality(admin: psycopg.Connection) -> None:
    """Декабрь в среднем сильнее февраля: на этом строятся вопросы про динамику."""
    ratio = scalar(
        admin,
        """
        SELECT avg(n) FILTER (WHERE m = 12) / avg(n) FILTER (WHERE m = 2)
        FROM (SELECT extract(month FROM created_at) m, date_trunc('month', created_at),
                     count(*) n
              FROM orders GROUP BY 1, 2) t
        """,
    )
    assert ratio > 1.5
