"""Генератор демо-БД Suhbat2DB.

Создаёт схему (schema.sql), заполняет её синтетическими, но правдоподобными данными
о продажах в Казахстане и настраивает роль агента только для чтения (roles.sql).

Повторный запуск идемпотентен: схема public пересоздаётся, а фиксированный seed
даёт одни и те же данные.

    uv run python seed.py              # полный объём (~100k заказов, 30k клиентов)
    uv run python seed.py --scale 0.05 # уменьшенный объём для CI
"""

from __future__ import annotations

import argparse
import os
import random
import time
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import accumulate
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import psycopg
from dotenv import load_dotenv
from faker import Faker
from psycopg import sql

HERE = Path(__file__).resolve().parent
SEED = 42
TZ = ZoneInfo("Asia/Almaty")
START = date(2023, 10, 1)
END = date(2026, 10, 18)  # данные «до вчерашнего дня» на момент создания набора
END_DT = datetime(END.year, END.month, END.day, 23, 59, tzinfo=TZ)

# --- Справочники -------------------------------------------------------------------------

# (id, название, тип, [(город, вес по населению)])
REGIONS: list[tuple[int, str, str, list[tuple[str, int]]]] = [
    (1, "Алматы", "city", [("Алматы", 25)]),
    (2, "Астана", "city", [("Астана", 20)]),
    (3, "Шымкент", "city", [("Шымкент", 10)]),
    (4, "Алматинская область", "oblast", [("Конаев", 2), ("Талгар", 2), ("Каскелен", 2)]),
    (5, "Карагандинская область", "oblast", [("Караганда", 7), ("Темиртау", 2)]),
    (6, "Актюбинская область", "oblast", [("Актобе", 5)]),
    (7, "Атырауская область", "oblast", [("Атырау", 4)]),
    (8, "Восточно-Казахстанская область", "oblast", [("Усть-Каменогорск", 4)]),
    (9, "Павлодарская область", "oblast", [("Павлодар", 4), ("Экибастуз", 1)]),
    (10, "Костанайская область", "oblast", [("Костанай", 3)]),
    (11, "Мангистауская область", "oblast", [("Актау", 3)]),
    (12, "Туркестанская область", "oblast", [("Туркестан", 2)]),
]

# (категория, [типы товаров], [бренды], (мин. цена, макс. цена), популярность)
CATEGORIES: list[tuple[str, list[str], list[str], tuple[int, int], float]] = [
    ("Смартфоны", ["Смартфон"], ["Samsung", "Apple", "Xiaomi", "Realme", "Honor"],
     (60_000, 700_000), 3.0),
    ("Ноутбуки", ["Ноутбук"], ["Lenovo", "HP", "ASUS", "Acer", "Apple"], (200_000, 1_200_000), 1.2),
    ("Телевизоры", ["Телевизор"], ["Samsung", "LG", "Xiaomi", "TCL", "Hisense"],
     (120_000, 900_000), 1.0),
    ("Бытовая техника", ["Холодильник", "Стиральная машина", "Пылесос", "Посудомоечная машина"],
     ["Samsung", "LG", "Bosch", "Indesit", "Dyson"], (40_000, 600_000), 1.3),
    ("Аксессуары", ["Наушники", "Чехол", "Зарядное устройство", "Пауэрбанк"],
     ["Apple", "Samsung", "Xiaomi", "Anker", "JBL"], (3_000, 80_000), 4.0),
    ("Товары для дома", ["Чайник", "Утюг", "Блендер", "Мультиварка"],
     ["Philips", "Tefal", "Redmond", "Bosch", "Polaris"], (8_000, 90_000), 2.0),
    ("Игровые консоли", ["Игровая консоль", "Геймпад", "Игра"],
     ["Sony", "Microsoft", "Nintendo"], (15_000, 350_000), 0.8),
    ("Фото и видео", ["Фотоаппарат", "Экшн-камера", "Объектив"],
     ["Canon", "Sony", "Nikon", "GoPro", "DJI"], (80_000, 900_000), 0.5),
    ("Умный дом", ["Умная колонка", "Умная лампа", "Камера видеонаблюдения", "Умная розетка"],
     ["Яндекс", "Xiaomi", "TP-Link", "Ezviz"], (5_000, 60_000), 1.5),
    ("Красота и здоровье", ["Фен", "Электробритва", "Электрическая зубная щётка", "Выпрямитель"],
     ["Philips", "Braun", "Dyson", "Rowenta", "Oral-B"], (8_000, 250_000), 1.2),
]  # fmt: skip
PRODUCTS_PER_CATEGORY = 20

KZ_FIRST_M = ["Алибек", "Данияр", "Ерлан", "Нурлан", "Асхат", "Бауыржан", "Алмас", "Ержан",
              "Темирлан", "Арман", "Санжар", "Дастан", "Мирас", "Айдос", "Руслан"]  # fmt: skip
KZ_FIRST_F = ["Айгерим", "Динара", "Асель", "Мадина", "Жанар", "Гульнара", "Аружан", "Камила",
              "Сауле", "Айжан", "Дана", "Алия", "Жансая", "Томирис", "Меруерт"]  # fmt: skip
KZ_LAST = ["Ахметов", "Сериков", "Нурланов", "Касымов", "Абенов", "Жаксылыков", "Бекетов",
           "Оспанов", "Тулегенов", "Исаев", "Мухамедов", "Садыков", "Есенов", "Омаров",
           "Жумабеков", "Калиев", "Байжанов", "Ибраев", "Смагулов", "Утепов"]  # fmt: skip
COMPANY_A = ["Альфа", "Береке", "Сункар", "Тенгри", "Нур", "Алтын", "Жулдыз", "Самал", "Достык",
             "Арман", "Кайнар", "Шанырак", "Мерей", "Байтерек", "Акжол"]  # fmt: skip
COMPANY_B = ["Трейд", "Сервис", "Строй", "Логистик", "Групп", "Технолоджи", "Инвест", "Маркет",
             "Систем", "Плюс"]  # fmt: skip

# Сезонность по месяцам: пик в ноябре (распродажи) и декабре (Новый год), спад летом
MONTH_WEIGHT = {1: 0.8, 2: 0.75, 3: 1.0, 4: 0.9, 5: 0.9, 6: 0.85,
                7: 0.8, 8: 0.95, 9: 1.0, 10: 1.0, 11: 1.4, 12: 1.6}  # fmt: skip
WEEKDAY_WEIGHT = [0.9, 0.9, 0.95, 1.0, 1.1, 1.3, 1.2]


# --- Модель данных генератора ------------------------------------------------------------


@dataclass
class Product:
    id: int
    name: str
    category_id: int
    price: int
    cost: int
    popularity: float
    discontinued_on: date | None


@dataclass
class Manager:
    id: int
    full_name: str
    region_id: int
    hired_at: date
    fired_at: date | None

    def active_on(self, d: date) -> bool:
        return self.hired_at <= d and (self.fired_at is None or d < self.fired_at)


@dataclass
class Customer:
    id: int
    full_name: str
    city_id: int
    region_id: int
    segment: str
    weight: float
    order_dates: list[datetime] = field(default_factory=list)


# --- Генерация -------------------------------------------------------------------------


class Generator:
    def __init__(self, scale: float) -> None:
        self.rng = random.Random(SEED)
        self.fake = Faker("ru_RU")
        self.fake.seed_instance(SEED)
        self.scale = scale
        self.rows: dict[str, list[tuple[Any, ...]]] = defaultdict(list)

    # Справочники

    def regions_and_cities(self) -> list[tuple[int, int, int]]:
        """Возвращает [(city_id, region_id, вес)] для выбора города клиента."""
        cities: list[tuple[int, int, int]] = []
        city_id = 1
        for region_id, name, region_type, region_cities in REGIONS:
            self.rows["regions"].append((region_id, name, region_type))
            for city_name, weight in region_cities:
                self.rows["cities"].append((city_id, city_name, region_id))
                cities.append((city_id, region_id, weight))
                city_id += 1
        return cities

    def products(self) -> list[Product]:
        products: list[Product] = []
        pid = 1
        for cat_id, (cat_name, kinds, brands, (lo, hi), popularity) in enumerate(CATEGORIES, 1):
            self.rows["categories"].append((cat_id, cat_name))
            for _ in range(PRODUCTS_PER_CATEGORY):
                kind, brand = self.rng.choice(kinds), self.rng.choice(brands)
                model = f"{self.rng.choice('ABCDEFGHKLMSX')}{self.rng.randint(10, 990)}"
                # логнормально внутри диапазона: дешёвых моделей больше, чем дорогих
                price = round(lo * (hi / lo) ** (self.rng.random() ** 1.6), -1) - 10
                cost = round(price * self.rng.uniform(0.6, 0.85))
                discontinued = self.rng.random() < 0.08
                discontinued_on = (
                    START + timedelta(days=self.rng.randint(200, (END - START).days - 60))
                    if discontinued
                    else None
                )
                products.append(
                    Product(pid, f"{kind} {brand} {model}", cat_id, int(price), cost,
                            popularity * self.rng.uniform(0.3, 1.7), discontinued_on)
                )  # fmt: skip
                self.rows["products"].append(
                    (pid, f"{kind} {brand} {model}", cat_id, int(price), cost, discontinued)
                )
                pid += 1
        return products

    def person_name(self) -> str:
        if self.rng.random() < 0.6:
            female = self.rng.random() < 0.5
            first = self.rng.choice(KZ_FIRST_F if female else KZ_FIRST_M)
            last = self.rng.choice(KZ_LAST) + ("а" if female else "")
            return f"{last} {first}"
        name: str = self.fake.name()
        return name

    def managers(self) -> dict[int, list[Manager]]:
        by_region: dict[int, list[Manager]] = defaultdict(list)
        mid = 1
        for region_id, _, _, region_cities in REGIONS:
            population = sum(w for _, w in region_cities)
            # минимум двое постоянных менеджеров на регион, чтобы магазин работал всегда
            permanent = max(2, round(population / 4))
            plans = ["permanent"] * permanent + ["fired"] * self.rng.randint(0, 2)
            plans += ["new"] * self.rng.randint(0, 2)
            for plan in plans:
                if plan == "new":
                    hired = START + timedelta(days=self.rng.randint(90, (END - START).days - 90))
                    fired = None
                else:
                    hired = date(2018, 1, 1) + timedelta(days=self.rng.randint(0, 2000))
                    fired = (
                        START + timedelta(days=self.rng.randint(60, (END - START).days - 60))
                        if plan == "fired"
                        else None
                    )
                m = Manager(mid, self.person_name(), region_id, hired, fired)
                by_region[region_id].append(m)
                self.rows["managers"].append((mid, m.full_name, region_id, hired, fired))
                mid += 1
        return by_region

    def customers(self, cities: list[tuple[int, int, int]]) -> list[Customer]:
        n = max(50, round(30_000 * self.scale))
        weights = [w for _, _, w in cities]
        customers: list[Customer] = []
        used_companies: set[str] = set()
        company_counts: dict[str, int] = defaultdict(int)
        for cid in range(1, n + 1):
            city_id, region_id, _ = self.rng.choices(cities, weights)[0]
            if self.rng.random() < 0.1:
                segment = "b2b"
                base = f"{self.rng.choice(COMPANY_A)} {self.rng.choice(COMPANY_B)}"
                # Цикл ниже определяет расход генератора случайных чисел, а от него зависят
                # все данные набора — поэтому он сохранён как есть. Имя для показа строится
                # отдельно: базовое название + порядковый номер («ТОО «Нур Трейд 3»»).
                key = f"ТОО «{base}»"
                while key in used_companies:
                    key = key[:-1] + f" {self.rng.randint(2, 99)}»"
                used_companies.add(key)
                company_counts[base] += 1
                n = company_counts[base]
                name = f"ТОО «{base}»" if n == 1 else f"ТОО «{base} {n}»"
            else:
                segment, name = "b2c", self.person_name()
            # распределение Парето: небольшая доля клиентов делает большую часть заказов
            weight = self.rng.paretovariate(1.3)
            customers.append(Customer(cid, name, city_id, region_id, segment, weight))
        return customers

    # Заказы

    def order_days(self, n: int) -> list[date]:
        days = [START + timedelta(days=i) for i in range((END - START).days + 1)]
        weights = []
        for d in days:
            trend = 1 + 0.25 * (d - START).days / 365  # рост сети ~25% в год
            special = 1.0
            if d.month == 11 and 20 <= d.day <= 30:
                special = 1.8  # «чёрная пятница»
            elif d.month == 12 and d.day >= 20:
                special = 1.6  # подарки к Новому году
            elif d.month == 3 and 1 <= d.day <= 7:
                special = 1.4  # к 8 Марта
            weights.append(trend * MONTH_WEIGHT[d.month] * WEEKDAY_WEIGHT[d.weekday()] * special)
        return sorted(self.rng.choices(days, weights, k=n))

    def timestamp(self, d: date, channel: str) -> datetime:
        if channel == "store":
            hour = self.rng.randint(10, 20)
        else:
            hour = self.rng.choices(range(24), [1] * 7 + [2] * 11 + [4] * 5 + [2])[0]
        return datetime(d.year, d.month, d.day, hour, self.rng.randint(0, 59),
                        self.rng.randint(0, 59), tzinfo=TZ)  # fmt: skip

    def unit_price(self, product: Product, d: date) -> int:
        # цены в прошлом ниже текущих: инфляция ~10% в год
        years_before_end = (END - d).days / 365
        return int(round(product.price / 1.1**years_before_end * self.rng.uniform(0.95, 1.05), -1))

    def orders(
        self,
        customers: list[Customer],
        products: list[Product],
        managers: dict[int, list[Manager]],
    ) -> None:
        n = max(500, round(100_000 * self.scale))
        # накопленные веса считаются один раз: иначе choices() пересчитывает их на каждый заказ
        cust_cum = list(accumulate(c.weight for c in customers))
        prod_cum = list(accumulate(p.popularity for p in products))
        payment_id = return_id = 1

        for oid, d in enumerate(self.order_days(n), 1):
            customer = self.rng.choices(customers, cum_weights=cust_cum)[0]
            b2b = customer.segment == "b2b"
            channel = "store" if self.rng.random() < (0.7 if b2b else 0.6) else "online"
            manager_id = None
            if channel == "store":
                active = [m for m in managers[customer.region_id] if m.active_on(d)]
                manager_id = self.rng.choice(active).id
            created = self.timestamp(d, channel)
            customer.order_dates.append(created)

            # позиции заказа
            n_lines = self.rng.choices([1, 2, 3, 4, 5], [55, 25, 12, 5, 3])[0]
            if b2b:
                n_lines = min(5, n_lines + 1)
            chosen: dict[int, Product] = {}
            while len(chosen) < n_lines:
                p = self.rng.choices(products, cum_weights=prod_cum)[0]
                if p.discontinued_on is None or d < p.discontinued_on:
                    chosen[p.id] = p
            subtotal = 0
            for p in chosen.values():
                qty = (
                    self.rng.randint(2, 20) if b2b else self.rng.choices([1, 2, 3], [85, 12, 3])[0]
                )
                price = self.unit_price(p, d)
                subtotal += qty * price
                self.rows["order_items"].append((oid, p.id, qty, price))

            discount = 0
            if self.rng.random() < 0.3:
                discount = int(round(subtotal * self.rng.uniform(0.03, 0.15), -2))
            total = subtotal - discount

            # платежи и статус
            status, payments = self.payments_and_status(created, channel, b2b, total)
            for paid_at, amount, method in payments:
                self.rows["payments"].append((payment_id, oid, paid_at, amount, method))
                payment_id += 1

            if status == "delivered" and self.rng.random() < 0.05:
                returned_at = created + timedelta(days=self.rng.randint(5, 40),
                                                  hours=self.rng.randint(0, 10))  # fmt: skip
                if returned_at < END_DT:
                    items = [r for r in self.rows["order_items"][-len(chosen) :]]
                    amount = (
                        total
                        if self.rng.random() < 0.6 or len(items) == 1
                        else min(total, items[0][2] * items[0][3])
                    )
                    reason = self.rng.choices(
                        ["defect", "not_as_described", "changed_mind", "late_delivery"],
                        [35, 20, 35, 10],
                    )[0]
                    self.rows["returns"].append((return_id, oid, returned_at, amount, reason))
                    return_id += 1

            self.rows["orders"].append(
                (oid, customer.id, manager_id, channel, status, created, discount, total)
            )

    def payments_and_status(
        self, created: datetime, channel: str, b2b: bool, total: int
    ) -> tuple[str, list[tuple[datetime, int, str]]]:
        if self.rng.random() < 0.06:
            return "cancelled", []

        if b2b:
            method = "bank_transfer"
            first = created + timedelta(days=self.rng.randint(1, 10), hours=self.rng.randint(0, 8))
        elif channel == "store":
            method = self.rng.choices(["card", "kaspi_qr", "cash"], [40, 45, 15])[0]
            first = created + timedelta(minutes=self.rng.randint(1, 10))
        else:
            method = self.rng.choices(["card", "kaspi_qr", "cash"], [45, 45, 10])[0]
            # наличные — при доставке, через 1–4 дня (оплата может попасть в другой квартал)
            delay = (
                timedelta(days=self.rng.randint(1, 4))
                if method == "cash"
                else timedelta(minutes=self.rng.randint(1, 30))
            )
            first = created + delay

        if first > END_DT:
            return "new", []

        payments = [(first, total, method)]
        if b2b and self.rng.random() < 0.3:
            # оплата частями: предоплата и остаток
            share = self.rng.choice([0.3, 0.5, 0.7])
            prepaid = int(round(total * share, -2))
            second = min(first + timedelta(days=self.rng.randint(7, 30)), END_DT)
            if prepaid > 0 and second > first:
                payments = [(first, prepaid, method), (second, total - prepaid, method)]

        age = (END_DT - created).days
        status = "paid" if age < 3 else "shipped" if age < 7 else "delivered"
        return status, payments

    def finalize_customers(self, customers: list[Customer]) -> None:
        year_ago = END_DT - timedelta(days=365)
        for c in customers:
            if c.order_dates:
                registered = min(c.order_dates) - timedelta(
                    days=self.rng.randint(0, 400), hours=self.rng.randint(0, 23)
                )
                is_active = max(c.order_dates) >= year_ago
            else:
                registered = datetime(2021, 1, 1, tzinfo=TZ) + timedelta(
                    days=self.rng.randint(0, (END - date(2021, 1, 1)).days)
                )
                is_active = False
            self.rows["customers"].append(
                (c.id, c.full_name, c.city_id, c.segment, is_active, registered)
            )

    def fiscal_calendar(self) -> None:
        d = date(2023, 1, 1)
        while d <= date(2027, 12, 31):
            cq = (d.month - 1) // 3 + 1
            fy = d.year if d.month >= 4 else d.year - 1
            fq = ((d.month - 4) % 12) // 3 + 1
            self.rows["fiscal_calendar"].append((d, d.year, cq, fy, fq))
            d += timedelta(days=1)

    def run(self) -> dict[str, list[tuple[Any, ...]]]:
        cities = self.regions_and_cities()
        products = self.products()
        managers = self.managers()
        customers = self.customers(cities)
        self.orders(customers, products, managers)
        self.finalize_customers(customers)
        self.fiscal_calendar()
        return self.rows


# --- Загрузка ----------------------------------------------------------------------------

COLUMNS: dict[str, Sequence[str]] = {
    "regions": ("id", "name", "region_type"),
    "cities": ("id", "name", "region_id"),
    "customers": ("id", "full_name", "city_id", "segment", "is_active", "registered_at"),
    "managers": ("id", "full_name", "region_id", "hired_at", "fired_at"),
    "categories": ("id", "name"),
    "products": ("id", "name", "category_id", "price", "cost", "is_discontinued"),
    "orders": ("id", "customer_id", "manager_id", "channel", "status", "created_at",
               "discount_amount", "total_amount"),
    "order_items": ("order_id", "product_id", "quantity", "unit_price"),
    "payments": ("id", "order_id", "paid_at", "amount", "method"),
    "returns": ("id", "order_id", "returned_at", "amount", "reason"),
    "fiscal_calendar": ("date", "calendar_year", "calendar_quarter", "fiscal_year",
                        "fiscal_quarter"),
}  # fmt: skip


def copy_rows(cur: psycopg.Cursor[Any], table: str, rows: Iterable[tuple[Any, ...]]) -> None:
    stmt = sql.SQL("COPY {} ({}) FROM STDIN").format(
        sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, COLUMNS[table]))
    )
    with cur.copy(stmt) as copy:
        for row in rows:
            copy.write_row(row)


def configure_reader(cur: psycopg.Cursor[Any], reader: str, password: str, database: str) -> None:
    exists = cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (reader,)).fetchone()
    stmt = (
        sql.SQL("ALTER ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}")
        if exists
        else sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}")
    )
    cur.execute(stmt.format(sql.Identifier(reader), sql.Literal(password)))
    cur.execute(
        sql.SQL(read_sql("roles.sql")).format(
            reader=sql.Identifier(reader), database=sql.Identifier(database)
        )
    )


def read_sql(name: str) -> str:
    # файлы из репозитория — доверенный SQL, а не пользовательский ввод
    return (HERE / name).read_text()


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise SystemExit(f"Не задана переменная окружения {name} (см. .env.example)")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Заполнить демо-БД Suhbat2DB")
    parser.add_argument("--scale", type=float, default=1.0, help="доля от полного объёма")
    args = parser.parse_args()

    load_dotenv(HERE.parent / ".env")
    database = env("TARGET_DB_NAME", "demo")
    conninfo = psycopg.conninfo.make_conninfo(
        host=env("TARGET_DB_HOST", "localhost"),
        port=env("TARGET_DB_PORT", "5443"),
        user=env("TARGET_DB_ADMIN_USER", "target_admin"),
        password=env("TARGET_DB_ADMIN_PASSWORD"),
        dbname=database,
    )

    started = time.perf_counter()
    rows = Generator(args.scale).run()
    generated = time.perf_counter()

    with psycopg.connect(conninfo) as conn, conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
        cur.execute("CREATE SCHEMA public")
        # «день» и «квартал» в запросах считаются по местному времени, а не по UTC
        cur.execute(
            sql.SQL("ALTER DATABASE {} SET timezone = 'Asia/Almaty'").format(
                sql.Identifier(database)
            )
        )
        cur.execute(read_sql("schema.sql"))
        for table in COLUMNS:
            copy_rows(cur, table, rows[table])
        configure_reader(
            cur,
            env("TARGET_DB_READER_USER", "s2d_reader"),
            env("TARGET_DB_READER_PASSWORD"),
            database,
        )
    with psycopg.connect(conninfo, autocommit=True) as conn:
        conn.execute("ANALYZE")

    print(f"Сгенерировано за {generated - started:.1f} с, загружено за "
          f"{time.perf_counter() - generated:.1f} с")  # fmt: skip
    for table in COLUMNS:
        print(f"  {table:<16} {len(rows[table]):>8}")


if __name__ == "__main__":
    main()
