"""Сборка ambiguous_ru: неоднозначные и однозначные вопросы к демо-БД с эталонным SQL.

Правила разметки — evals/datasets/ambiguous_ru/GUIDELINES.md. Коротко:
- вопрос неоднозначен, только если разумные трактовки дают РАЗНЫЕ ответы — это
  проверяется выполнением эталонов, а не на глаз;
- однозначные вопросы следуют тем же умолчаниям, что знает агент (промпт ambiguity.md):
  выручка — сумма заказов без отменённых, «2025 год» — календарный;
- даты только абсолютные: ответ не должен зависеть от дня прогона;
- у неоднозначного вопроса одна «задуманная» трактовка (target): её выбирает
  симулированный пользователь, с её эталоном сравнивается ответ агента.

    cd backend && uv run python -m evals.build_ambiguous
"""

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import asyncpg
from dotenv import load_dotenv

from evals.metrics import has_order_by, results_equal
from evals.paths import DATASETS, ROOT, target_url

# --- Строительные блоки SQL ----------------------------------------------------------------

Period = Callable[[str], str]
NOT_CANCELLED = "o.status <> 'cancelled'"
REGION_JOIN = (
    "JOIN customers c ON c.id = o.customer_id "
    "JOIN cities ci ON ci.id = c.city_id JOIN regions r ON r.id = ci.region_id"
)
ITEMS_JOIN = (
    "JOIN order_items oi ON oi.order_id = o.id JOIN products p ON p.id = oi.product_id "
    "JOIN categories cat ON cat.id = p.category_id"
)
MONTHS = {
    1: "январе", 2: "феврале", 3: "марте", 4: "апреле", 5: "мае", 6: "июне",
    7: "июле", 8: "августе", 9: "сентябре", 10: "октябре", 11: "ноябре", 12: "декабре",
}  # fmt: skip
QUARTER_WORDS = {1: "первый", 2: "второй", 3: "третий", 4: "четвёртый"}
QUARTER_WORDS_PREP = {1: "первом", 2: "втором", 3: "третьем", 4: "четвёртом"}


def between(col: str, start: str, end: str) -> str:
    return f"{col} >= '{start}' AND {col} < '{end}'"


def cal_year(col: str, y: int) -> str:
    return between(col, f"{y}-01-01", f"{y + 1}-01-01")


def fiscal_year(col: str, y: int) -> str:
    return between(col, f"{y}-04-01", f"{y + 1}-04-01")


def month_start(y: int, m: int) -> str:
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return f"{y}-{m:02d}-01"


def cal_quarter(col: str, y: int, q: int) -> str:
    return between(col, month_start(y, 3 * q - 2), month_start(y, 3 * q + 1))


def fiscal_quarter(col: str, y: int, q: int) -> str:
    """FQ1 финансового года Y — апрель–июнь Y; FQ4 — январь–март Y+1."""
    return between(col, month_start(y, 3 * q + 1), month_start(y, 3 * q + 4))


def month(col: str, y: int, m: int) -> str:
    return between(col, month_start(y, m), month_start(y, m + 1))


def where(*conds: str) -> str:
    return " AND ".join(c for c in conds if c)


def revenue(cond: str, join: str = "") -> str:
    return f"SELECT SUM(o.total_amount) AS revenue FROM orders o {join} WHERE {where(NOT_CANCELLED, cond)}"


def orders_count(cond: str, join: str = "", *, include_cancelled: bool = False) -> str:
    base = "" if include_cancelled else NOT_CANCELLED
    return f"SELECT COUNT(*) AS orders FROM orders o {join} WHERE {where(base, cond)}"


def units(cond: str, join: str = "") -> str:
    return (
        "SELECT SUM(oi.quantity) AS units FROM orders o "
        f"JOIN order_items oi ON oi.order_id = o.id {join} WHERE {where(NOT_CANCELLED, cond)}"
    )


def avg_check(cond: str, join: str = "") -> str:
    return f"SELECT ROUND(AVG(o.total_amount), 2) AS avg_check FROM orders o {join} WHERE {where(NOT_CANCELLED, cond)}"


ALMATY_CITY = "r.name = 'Алматы'"
ALMATY_ALL = "r.name IN ('Алматы', 'Алматинская область')"

# --- Разметка ------------------------------------------------------------------------------


@dataclass
class Item:
    question: str
    interpretations: list[tuple[str | None, str]]  # (ответ на уточнение, эталонный SQL)
    types: list[str] = field(default_factory=list)
    target: int = 0

    @property
    def ambiguous(self) -> bool:
        return len(self.interpretations) > 1


def clear(question: str, sql: str) -> Item:
    return Item(question, [(None, sql)])


def items() -> list[Item]:
    out: list[Item] = []

    # 1. metric: «продажи» — выручка / заказы / единицы (период однозначен)
    metric_periods: list[tuple[str, Period]] = [
        ("за 2025 год", lambda col: cal_year(col, 2025)),
        ("за 2024 год", lambda col: cal_year(col, 2024)),
        ("в марте 2026 года", lambda col: month(col, 2026, 3)),
        ("в декабре 2025 года", lambda col: month(col, 2025, 12)),
        ("в августе 2026 года", lambda col: month(col, 2026, 8)),
        ("в мае 2025 года", lambda col: month(col, 2025, 5)),
        ("в феврале 2026 года", lambda col: month(col, 2026, 2)),
        ("в октябре 2025 года", lambda col: month(col, 2025, 10)),
        ("в ноябре 2024 года", lambda col: month(col, 2024, 11)),
        ("в июне 2026 года", lambda col: month(col, 2026, 6)),
    ]
    for i, (words, period) in enumerate(metric_periods):
        cond = period("o.created_at")
        out.append(
            Item(
                f"Покажи продажи {words}",
                [
                    ("выручка — сумма заказов без отменённых", revenue(cond)),
                    ("количество заказов без отменённых", orders_count(cond)),
                    ("проданные единицы товара", units(cond)),
                ],
                ["metric"],
                target=i % 3,
            )
        )
    category_periods: list[tuple[str, str, Period]] = [
        ("Смартфоны", "смартфонов за 2025 год", lambda c: cal_year(c, 2025)),
        ("Ноутбуки", "ноутбуков в 2026 году", lambda c: cal_year(c, 2026)),
        ("Телевизоры", "телевизоров за 2024 год", lambda c: cal_year(c, 2024)),
        ("Бытовая техника", "бытовой техники в июле 2026", lambda c: month(c, 2026, 7)),
    ]
    for i, (category, words, period) in enumerate(category_periods):
        cond = where(period("o.created_at"), f"cat.name = '{category}'")
        out.append(
            Item(
                f"Какие продажи {words}?",
                [
                    (
                        "выручка по позициям: количество × цена продажи",
                        f"SELECT SUM(oi.quantity * oi.unit_price) AS revenue FROM orders o {ITEMS_JOIN} "
                        f"WHERE {where(NOT_CANCELLED, cond)}",
                    ),
                    (
                        "число заказов с этими товарами",
                        f"SELECT COUNT(DISTINCT o.id) AS orders FROM orders o {ITEMS_JOIN} "
                        f"WHERE {where(NOT_CANCELLED, cond)}",
                    ),
                    (
                        "проданные единицы",
                        f"SELECT SUM(oi.quantity) AS units FROM orders o {ITEMS_JOIN} "
                        f"WHERE {where(NOT_CANCELLED, cond)}",
                    ),
                ],
                ["metric"],
                target=(i + 1) % 3,
            )
        )
    for i, year in enumerate([2024, 2025]):
        cond = cal_year("o.created_at", year)
        out.append(
            Item(
                f"Продажи по категориям за {year} год",
                [
                    (
                        "выручка по позициям: количество × цена продажи",
                        f"SELECT cat.name AS category, SUM(oi.quantity * oi.unit_price) AS revenue "
                        f"FROM orders o {ITEMS_JOIN} WHERE {where(NOT_CANCELLED, cond)} GROUP BY cat.name",
                    ),
                    (
                        "проданные единицы",
                        f"SELECT cat.name AS category, SUM(oi.quantity) AS units "
                        f"FROM orders o {ITEMS_JOIN} WHERE {where(NOT_CANCELLED, cond)} GROUP BY cat.name",
                    ),
                ],
                ["metric"],
                target=i % 2,
            )
        )
    top_periods: list[tuple[str, Period]] = [
        ("за 2025 год", lambda c: cal_year(c, 2025)),
        ("в 2026 году", lambda c: cal_year(c, 2026)),
    ]
    for i, (words, period) in enumerate(top_periods):
        cond = period("o.created_at")
        out.append(
            Item(
                f"Какие 5 товаров самые популярные {words}?",
                [
                    (
                        "по проданным единицам",
                        f"SELECT p.name AS product, SUM(oi.quantity) AS units FROM orders o {ITEMS_JOIN} "
                        f"WHERE {where(NOT_CANCELLED, cond)} GROUP BY p.name ORDER BY units DESC LIMIT 5",
                    ),
                    (
                        "по выручке",
                        f"SELECT p.name AS product, SUM(oi.quantity * oi.unit_price) AS revenue "
                        f"FROM orders o {ITEMS_JOIN} WHERE {where(NOT_CANCELLED, cond)} "
                        "GROUP BY p.name ORDER BY revenue DESC LIMIT 5",
                    ),
                ],
                ["metric"],
                target=i % 2,
            )
        )

    # 2. temporal: квартал календарный или финансовый (FY начинается 1 апреля)
    quarter_cases = [
        (2026, 1), (2025, 2), (2025, 3), (2025, 4), (2024, 4), (2026, 2), (2024, 3), (2025, 1),
    ]  # fmt: skip
    for i, (y, q) in enumerate(quarter_cases):
        out.append(
            Item(
                f"Выручка за {QUARTER_WORDS[q]} квартал {y} года",
                [
                    ("календарный квартал", revenue(cal_quarter("o.created_at", y, q))),
                    (
                        "финансовый квартал, год с 1 апреля",
                        revenue(fiscal_quarter("o.created_at", y, q)),
                    ),
                ],
                ["temporal"],
                target=i % 2,
            )
        )
    for i, (y, q) in enumerate([(2025, 1), (2025, 3), (2026, 2), (2024, 4)]):
        out.append(
            Item(
                f"Сколько заказов было оформлено в {QUARTER_WORDS_PREP[q]} квартале {y} года?",
                [
                    (
                        "календарный квартал",
                        orders_count(cal_quarter("o.created_at", y, q), include_cancelled=True),
                    ),
                    (
                        "финансовый квартал",
                        orders_count(fiscal_quarter("o.created_at", y, q), include_cancelled=True),
                    ),
                ],
                ["temporal"],
                target=(i + 1) % 2,
            )
        )
    for i, (y, q) in enumerate([(2025, 2), (2026, 1)]):
        cond_cal = cal_quarter("o.created_at", y, q)
        cond_fis = fiscal_quarter("o.created_at", y, q)
        out.append(
            Item(
                f"Покажи продажи за {QUARTER_WORDS[q]} квартал {y}",
                [
                    ("выручка, календарный квартал", revenue(cond_cal)),
                    ("выручка, финансовый квартал", revenue(cond_fis)),
                    ("число заказов без отменённых, календарный квартал", orders_count(cond_cal)),
                    ("число заказов без отменённых, финансовый квартал", orders_count(cond_fis)),
                ],
                ["metric", "temporal"],
                target=(i * 3) % 4,
            )
        )

    # 3. value: «Алматы» — город или город с областью
    almaty_cases = [
        ("Выручка в Алматы за 2025 год", revenue, cal_year("o.created_at", 2025)),
        ("Выручка в Алматы за 2024 год", revenue, cal_year("o.created_at", 2024)),
        ("Сколько заказов из Алматы в 2026 году без отменённых?", orders_count, cal_year("o.created_at", 2026)),
        ("Средний чек в Алматы за 2025 год", avg_check, cal_year("o.created_at", 2025)),
        ("Выручка в Алматы в сентябре 2026 года", revenue, month("o.created_at", 2026, 9)),
        ("Выручка в Алматы за 2026 год", revenue, cal_year("o.created_at", 2026)),
        ("Сколько заказов из Алматы в 2025 году без отменённых?", orders_count, cal_year("o.created_at", 2025)),
    ]  # fmt: skip
    for i, (question, metric, cond) in enumerate(almaty_cases):
        out.append(
            Item(
                question,
                [
                    ("только город Алматы", metric(where(cond, ALMATY_CITY), REGION_JOIN)),
                    (
                        "Алматы вместе с Алматинской областью",
                        metric(where(cond, ALMATY_ALL), REGION_JOIN),
                    ),
                ],
                ["value"],
                target=i % 2,
            )
        )
    customers_region = (
        "SELECT COUNT(*) AS customers FROM customers c JOIN cities ci ON ci.id = c.city_id "
        "JOIN regions r ON r.id = ci.region_id WHERE "
    )
    out.append(
        Item(
            "Сколько клиентов из Алматы?",
            [
                ("только город Алматы", customers_region + ALMATY_CITY),
                ("Алматы вместе с Алматинской областью", customers_region + ALMATY_ALL),
            ],
            ["value"],
            target=1,
        )
    )

    # 4. scope: «лучший менеджер» — по выручке или по числу заказов
    mgr = (
        "SELECT m.full_name AS manager, {metric} AS value FROM orders o "
        "JOIN managers m ON m.id = o.manager_id {join}WHERE {cond} "
        "GROUP BY m.id, m.full_name ORDER BY value DESC LIMIT {n}"
    )
    manager_cases = [
        ("Кто лучший менеджер за 2025 год?", cal_year("o.created_at", 2025), 1, ""),
        ("Кто лучший менеджер за 2024 год?", cal_year("o.created_at", 2024), 1, ""),
        ("Топ-5 менеджеров за 2026 год", cal_year("o.created_at", 2026), 5, ""),
        ("Топ-3 менеджера за 2025 год", cal_year("o.created_at", 2025), 3, ""),
        ("Лучший менеджер в Астане за 2025 год", where(cal_year("o.created_at", 2025), "r.name = 'Астана'"), 1, "JOIN regions r ON r.id = m.region_id "),
        ("Лучший менеджер в Шымкенте за 2026 год", where(cal_year("o.created_at", 2026), "r.name = 'Шымкент'"), 1, "JOIN regions r ON r.id = m.region_id "),
    ]  # fmt: skip
    for i, (question, cond, n, join) in enumerate(manager_cases):
        full = where(NOT_CANCELLED, cond)
        out.append(
            Item(
                question,
                [
                    (
                        "по выручке",
                        mgr.format(metric="SUM(o.total_amount)", join=join, cond=full, n=n),
                    ),
                    ("по числу заказов", mgr.format(metric="COUNT(*)", join=join, cond=full, n=n)),
                ],
                ["scope"],
                target=i % 2,
            )
        )

    # 5. scope: «клиенты» — все зарегистрированные / покупавшие / активные
    bought = (
        "EXISTS (SELECT 1 FROM orders o WHERE o.customer_id = c.id AND o.status <> 'cancelled')"
    )
    customer_cases = [
        ("Сколько у нас клиентов?", ""),
        ("Сколько клиентов-организаций?", "c.segment = 'b2b'"),
        ("Сколько клиентов — физических лиц?", "c.segment = 'b2c'"),
        ("Сколько клиентов в Шымкенте?", "r.name = 'Шымкент'"),
        ("Сколько клиентов в Карагандинской области?", "r.name = 'Карагандинская область'"),
        ("Сколько клиентов в Астане?", "r.name = 'Астана'"),
    ]
    for i, (question, extra) in enumerate(customer_cases):
        join = (
            "JOIN cities ci ON ci.id = c.city_id JOIN regions r ON r.id = ci.region_id "
            if "r." in extra
            else ""
        )
        base = f"SELECT COUNT(*) AS customers FROM customers c {join}"
        out.append(
            Item(
                question,
                [
                    ("все зарегистрированные", base + (f"WHERE {extra}" if extra else "")),
                    ("те, кто сделал хотя бы один заказ", base + f"WHERE {where(extra, bought)}"),
                    ("активные клиенты (is_active)", base + f"WHERE {where(extra, 'c.is_active')}"),
                ],
                ["scope"],
                target=i % 3,
            )
        )

    # 6. schema: цена текущая (products.price) или на момент продажи (order_items.unit_price)
    price_cases = [
        ("Смартфоны", "смартфонов", 2025),
        ("Ноутбуки", "ноутбуков", 2025),
        ("Телевизоры", "телевизоров", 2026),
        ("Игровые консоли", "игровых консолей", 2024),
        ("Фото и видео", "товаров для фото и видео", 2025),
        ("Аксессуары", "аксессуаров", 2026),
    ]
    for i, (category, words, year) in enumerate(price_cases):
        cond = where(NOT_CANCELLED, cal_year("o.created_at", year), f"cat.name = '{category}'")
        out.append(
            Item(
                f"Средняя цена проданных {words} в {year} году",
                [
                    (
                        "цена на момент продажи (order_items.unit_price)",
                        f"SELECT ROUND(AVG(oi.unit_price), 2) AS avg_price FROM orders o {ITEMS_JOIN} WHERE {cond}",
                    ),
                    (
                        "текущая цена из каталога (products.price)",
                        f"SELECT ROUND(AVG(p.price), 2) AS avg_price FROM orders o {ITEMS_JOIN} WHERE {cond}",
                    ),
                ],
                ["schema"],
                target=i % 2,
            )
        )

    # 7. temporal: дата заказа или дата оплаты («поступления»)
    for i, (y, m) in enumerate([(2026, 9), (2025, 12), (2026, 3), (2025, 6)]):
        out.append(
            Item(
                f"Сколько денег мы получили в {MONTHS[m]} {y} года?",
                [
                    ("по дате оплаты: сумма платежей", f"SELECT SUM(p.amount) AS paid FROM payments p WHERE {month('p.paid_at', y, m)}"),
                    ("по дате заказа: выручка без отменённых", revenue(month("o.created_at", y, m))),
                ],
                ["temporal"],
                target=i % 2,
            )
        )  # fmt: skip

    # --- Однозначные: явный показатель, период и значения --------------------------------
    clears = [
        clear("Выручка за 2025 год", revenue(cal_year("o.created_at", 2025))),
        clear("Выручка за 2024 год", revenue(cal_year("o.created_at", 2024))),
        clear("Какая выручка за финансовый 2025 год?", revenue(fiscal_year("o.created_at", 2025))),
        clear("Выручка за финансовый 2024 год", revenue(fiscal_year("o.created_at", 2024))),
        clear("Выручка за первый календарный квартал 2026 года", revenue(cal_quarter("o.created_at", 2026, 1))),
        clear("Выручка за второй финансовый квартал 2025 года", revenue(fiscal_quarter("o.created_at", 2025, 2))),
        clear("Сколько заказов оформлено в сентябре 2026?", orders_count(month("o.created_at", 2026, 9), include_cancelled=True)),
        clear("Сколько заказов оформлено в январе 2025 года?", orders_count(month("o.created_at", 2025, 1), include_cancelled=True)),
        clear("Сколько отменённых заказов было в 2025 году?", "SELECT COUNT(*) AS cancelled FROM orders o WHERE o.status = 'cancelled' AND " + cal_year("o.created_at", 2025)),
        clear("Сколько единиц товара продано в 2025 году?", units(cal_year("o.created_at", 2025))),
        clear("Сколько единиц смартфонов продано в 2026 году?", f"SELECT SUM(oi.quantity) AS units FROM orders o {ITEMS_JOIN} WHERE {where(NOT_CANCELLED, cal_year('o.created_at', 2026), "cat.name = 'Смартфоны'")}"),
        # формулировки не совпадают с few-shot примерами агента (app/agent/examples/demo.json)
        clear("Количество заказов без отменённых по регионам клиентов за 2024 год", f"SELECT r.name AS region, COUNT(*) AS orders FROM orders o {REGION_JOIN} WHERE {where(NOT_CANCELLED, cal_year('o.created_at', 2024))} GROUP BY r.name"),
        clear("Выручка в городе Алматы (без области) за 2025 год", revenue(where(cal_year("o.created_at", 2025), ALMATY_CITY), REGION_JOIN)),
        clear("Выручка в Алматинской области без города Алматы за 2025 год", revenue(where(cal_year("o.created_at", 2025), "r.name = 'Алматинская область'"), REGION_JOIN)),
        clear("Выручка в Астане за 2025 год", revenue(where(cal_year("o.created_at", 2025), "r.name = 'Астана'"), REGION_JOIN)),
        clear("Средний чек онлайн и в магазинах за 2025 год", f"SELECT o.channel, ROUND(AVG(o.total_amount), 2) AS avg_check FROM orders o WHERE {where(NOT_CANCELLED, cal_year('o.created_at', 2025))} GROUP BY o.channel"),
        clear("Средний чек за 2026 год", avg_check(cal_year("o.created_at", 2026))),
        clear("Сколько заказов оформлялось в каждом месяце 2025 года, включая отменённые?", f"SELECT date_trunc('month', o.created_at) AS month, COUNT(*) AS orders FROM orders o WHERE {cal_year('o.created_at', 2025)} GROUP BY 1 ORDER BY 1"),
        clear("Количество заказов по каналам продаж за 2026 год", f"SELECT o.channel, COUNT(*) AS orders FROM orders o WHERE {where(NOT_CANCELLED, cal_year('o.created_at', 2026))} GROUP BY o.channel"),
        clear("Какой способ оплаты самый популярный по числу платежей?", "SELECT p.method, COUNT(*) AS payments FROM payments p GROUP BY p.method ORDER BY payments DESC LIMIT 1"),
        clear("Сумма платежей по способам оплаты за 2025 год", f"SELECT p.method, SUM(p.amount) AS paid FROM payments p WHERE {cal_year('p.paid_at', 2025)} GROUP BY p.method"),
        clear("Сколько возвратов было в 2025 году?", f"SELECT COUNT(*) AS returns FROM returns rt WHERE {cal_year('rt.returned_at', 2025)}"),
        clear("Сколько возвратов было по каждой причине в 2026 году?", f"SELECT rt.reason, COUNT(*) AS returns FROM returns rt WHERE {cal_year('rt.returned_at', 2026)} GROUP BY rt.reason"),
        clear("Сколько возвратов из-за брака было в 2026 году?", f"SELECT COUNT(*) AS returns FROM returns rt WHERE rt.reason = 'defect' AND {cal_year('rt.returned_at', 2026)}"),
        clear("Сколько клиентов зарегистрировано всего?", "SELECT COUNT(*) AS customers FROM customers c"),
        clear("Сколько клиентов сделали хотя бы один заказ?", "SELECT COUNT(*) AS customers FROM customers c WHERE " + bought.replace(" AND o.status <> 'cancelled'", "")),
        clear("Сколько активных клиентов?", "SELECT COUNT(*) AS customers FROM customers c WHERE c.is_active"),
        clear("Сколько клиентов-организаций (b2b) зарегистрировано?", "SELECT COUNT(*) AS customers FROM customers c WHERE c.segment = 'b2b'"),
        clear("Сколько клиентов зарегистрировалось в 2025 году?", "SELECT COUNT(*) AS customers FROM customers c WHERE " + cal_year("c.registered_at", 2025)),
        clear("Какой менеджер принёс больше всего выручки в 2026 году?", mgr.format(metric="SUM(o.total_amount)", join="", cond=where(NOT_CANCELLED, cal_year("o.created_at", 2026)), n=1)),
        clear("Топ-3 менеджера по числу заказов за 2026 год", mgr.format(metric="COUNT(*)", join="", cond=where(NOT_CANCELLED, cal_year("o.created_at", 2026)), n=3)),
        clear("Сколько менеджеров уволено?", "SELECT COUNT(*) AS fired FROM managers m WHERE m.fired_at IS NOT NULL"),
        clear("Сколько менеджеров уволено в каждом регионе?", "SELECT r.name AS region, COUNT(*) AS fired FROM managers m JOIN regions r ON r.id = m.region_id WHERE m.fired_at IS NOT NULL GROUP BY r.name"),
        clear("Сколько товаров снято с продажи?", "SELECT COUNT(*) AS discontinued FROM products p WHERE p.is_discontinued"),
        clear("Сколько товаров в каждой категории?", "SELECT cat.name AS category, COUNT(*) AS products FROM products p JOIN categories cat ON cat.id = p.category_id GROUP BY cat.name"),
        clear("Средняя текущая цена смартфонов в каталоге", "SELECT ROUND(AVG(p.price), 2) AS avg_price FROM products p JOIN categories cat ON cat.id = p.category_id WHERE cat.name = 'Смартфоны'"),
        clear("Средняя цена продажи ноутбуков в 2025 году по позициям заказов", f"SELECT ROUND(AVG(oi.unit_price), 2) AS avg_price FROM orders o {ITEMS_JOIN} WHERE {where(NOT_CANCELLED, cal_year('o.created_at', 2025), "cat.name = 'Ноутбуки'")}"),
        clear("Какой самый дорогой товар в каталоге?", "SELECT p.name, p.price FROM products p ORDER BY p.price DESC LIMIT 1"),
        clear("Сумма скидок по заказам за 2025 год", f"SELECT SUM(o.discount_amount) AS discounts FROM orders o WHERE {where(NOT_CANCELLED, cal_year('o.created_at', 2025))}"),
        clear("Выручка онлайн-заказов за 2024 год", revenue(where(cal_year("o.created_at", 2024), "o.channel = 'online'"))),
        clear("Сколько заказов сейчас в статусе «отгружен»?", "SELECT COUNT(*) AS orders FROM orders o WHERE o.status = 'shipped'"),
        clear("Выручка по категориям товаров за 2026 год по позициям заказов", f"SELECT cat.name AS category, SUM(oi.quantity * oi.unit_price) AS revenue FROM orders o {ITEMS_JOIN} WHERE {where(NOT_CANCELLED, cal_year('o.created_at', 2026))} GROUP BY cat.name"),
        clear("Сколько городов в базе?", "SELECT COUNT(*) AS cities FROM cities"),
        clear("Выручка от организаций (b2b) за 2025 год", revenue(where(cal_year("o.created_at", 2025), "c.segment = 'b2b'"), "JOIN customers c ON c.id = o.customer_id")),
    ]  # fmt: skip
    return out + clears


async def build() -> None:
    import os

    pool = await asyncpg.create_pool(
        target_url(os.environ.get("TARGET_DB_NAME", "demo")),
        min_size=1,
        max_size=4,
        server_settings={"statement_timeout": "30s"},
    )
    rows: list[dict[str, Any]] = []
    problems: list[str] = []
    try:
        for n, item in enumerate(items(), 1):
            results: list[list[tuple[Any, ...]] | None] = []
            for _, sql in item.interpretations:
                try:
                    async with pool.acquire() as conn:
                        results.append([tuple(r.values()) for r in await conn.fetch(sql)])
                except asyncpg.PostgresError as e:
                    problems.append(f"{item.question}: {e}")
                    results.append(None)
            if any(r is None or not r for r in results):
                problems.append(f"пустой или ошибочный эталон: {item.question}")
                continue
            done = [r for r in results if r is not None]
            if item.ambiguous:
                # неоднозначность реальна, только если ответы трактовок различаются
                for i in range(len(done)):
                    for j in range(i + 1, len(done)):
                        sql_i = item.interpretations[i][1]
                        if results_equal(done[i], done[j], has_order_by(sql_i)):
                            problems.append(f"трактовки {i} и {j} совпадают: {item.question}")
            kind = "amb" if item.ambiguous else "clear"
            rows.append(
                {
                    "id": f"ambiguous_ru-{kind}-{n:03d}",
                    "question": item.question,
                    "is_ambiguous": item.ambiguous,
                    "ambiguity_types": item.types,
                    "target": item.target,
                    "interpretations": [
                        {"answer_to_clarification": answer, "gold_sql": sql}
                        for answer, sql in item.interpretations
                    ],
                }
            )
    finally:
        await pool.close()
    if problems:
        raise SystemExit("Разметка не прошла проверку:\n" + "\n".join(problems))
    out = DATASETS / "ambiguous_ru" / "ambiguous_ru.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    amb = sum(r["is_ambiguous"] for r in rows)
    print(json.dumps({"ambiguous": amb, "clear": len(rows) - amb, "total": len(rows)}))


def main() -> None:
    load_dotenv(ROOT / ".env")
    asyncio.run(build())


if __name__ == "__main__":
    main()
