-- Демо-БД Suhbat2DB: продажи розничной сети электроники и товаров для дома в Казахстане.
-- Схема намеренно содержит источники неоднозначности (см. docs/demo_db.md).
-- Идентификаторы — на английском, значения и комментарии — на русском (с английским переводом).

CREATE TABLE regions (
    id          smallint PRIMARY KEY,
    name        text NOT NULL UNIQUE,
    region_type text NOT NULL CHECK (region_type IN ('city', 'oblast'))
);
COMMENT ON TABLE regions IS 'Регионы Казахстана: области и города республиканского значения / Regions of Kazakhstan: oblasts and cities of republican significance';
COMMENT ON COLUMN regions.id IS 'Идентификатор региона / Region ID';
COMMENT ON COLUMN regions.name IS 'Название региона, например «Алматы» (город) или «Алматинская область» / Region name';
COMMENT ON COLUMN regions.region_type IS 'Тип региона: city — город республиканского значения, oblast — область / Region type';

CREATE TABLE cities (
    id        smallint PRIMARY KEY,
    name      text NOT NULL,
    region_id smallint NOT NULL REFERENCES regions (id),
    UNIQUE (name, region_id)
);
COMMENT ON TABLE cities IS 'Города, в которых живут клиенты и работают магазины / Cities where customers live and stores operate';
COMMENT ON COLUMN cities.id IS 'Идентификатор города / City ID';
COMMENT ON COLUMN cities.name IS 'Название города / City name';
COMMENT ON COLUMN cities.region_id IS 'Регион, к которому относится город / Region the city belongs to';

CREATE TABLE customers (
    id            integer PRIMARY KEY,
    full_name     text NOT NULL,
    city_id       smallint NOT NULL REFERENCES cities (id),
    segment       text NOT NULL CHECK (segment IN ('b2c', 'b2b')),
    is_active     boolean NOT NULL,
    registered_at timestamptz NOT NULL
);
COMMENT ON TABLE customers IS 'Клиенты сети: физические лица (b2c) и организации (b2b) / Customers: individuals (b2c) and companies (b2b)';
COMMENT ON COLUMN customers.id IS 'Идентификатор клиента / Customer ID';
COMMENT ON COLUMN customers.full_name IS 'ФИО физического лица или название организации / Person full name or company name';
COMMENT ON COLUMN customers.city_id IS 'Город клиента / Customer city';
COMMENT ON COLUMN customers.segment IS 'Сегмент: b2c — физическое лицо, b2b — организация / Segment';
COMMENT ON COLUMN customers.is_active IS 'Активный клиент: совершал заказы за последние 12 месяцев / Active: ordered within the last 12 months';
COMMENT ON COLUMN customers.registered_at IS 'Дата регистрации клиента / Customer registration timestamp';

CREATE TABLE managers (
    id        smallint PRIMARY KEY,
    full_name text NOT NULL,
    region_id smallint NOT NULL REFERENCES regions (id),
    hired_at  date NOT NULL,
    fired_at  date CHECK (fired_at IS NULL OR fired_at > hired_at)
);
COMMENT ON TABLE managers IS 'Менеджеры по продажам в офлайн-магазинах / Store sales managers';
COMMENT ON COLUMN managers.id IS 'Идентификатор менеджера / Manager ID';
COMMENT ON COLUMN managers.full_name IS 'ФИО менеджера / Manager full name';
COMMENT ON COLUMN managers.region_id IS 'Регион, за который отвечает менеджер / Manager region';
COMMENT ON COLUMN managers.hired_at IS 'Дата приёма на работу / Hire date';
COMMENT ON COLUMN managers.fired_at IS 'Дата увольнения; NULL — работает сейчас / Termination date, NULL if currently employed';

CREATE TABLE categories (
    id   smallint PRIMARY KEY,
    name text NOT NULL UNIQUE
);
COMMENT ON TABLE categories IS 'Категории товаров / Product categories';
COMMENT ON COLUMN categories.id IS 'Идентификатор категории / Category ID';
COMMENT ON COLUMN categories.name IS 'Название категории / Category name';

CREATE TABLE products (
    id              integer PRIMARY KEY,
    name            text NOT NULL,
    category_id     smallint NOT NULL REFERENCES categories (id),
    price           numeric(12, 2) NOT NULL CHECK (price > 0),
    cost            numeric(12, 2) NOT NULL CHECK (cost > 0),
    is_discontinued boolean NOT NULL DEFAULT false
);
COMMENT ON TABLE products IS 'Товары / Products';
COMMENT ON COLUMN products.id IS 'Идентификатор товара / Product ID';
COMMENT ON COLUMN products.name IS 'Название товара / Product name';
COMMENT ON COLUMN products.category_id IS 'Категория товара / Product category';
COMMENT ON COLUMN products.price IS 'Текущая розничная цена в тенге / Current retail price, KZT';
COMMENT ON COLUMN products.cost IS 'Себестоимость единицы в тенге / Unit cost, KZT';
COMMENT ON COLUMN products.is_discontinued IS 'Товар снят с продажи / Product is discontinued';

CREATE TABLE orders (
    id              integer PRIMARY KEY,
    customer_id     integer NOT NULL REFERENCES customers (id),
    manager_id      smallint REFERENCES managers (id),
    channel         text NOT NULL CHECK (channel IN ('online', 'store')),
    status          text NOT NULL CHECK (status IN ('new', 'paid', 'shipped', 'delivered', 'cancelled')),
    created_at      timestamptz NOT NULL,
    discount_amount numeric(14, 2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    total_amount    numeric(14, 2) NOT NULL CHECK (total_amount >= 0),
    CHECK ((channel = 'online') = (manager_id IS NULL))
);
COMMENT ON TABLE orders IS 'Заказы покупателей / Customer orders';
COMMENT ON COLUMN orders.id IS 'Идентификатор заказа / Order ID';
COMMENT ON COLUMN orders.customer_id IS 'Клиент, оформивший заказ / Customer who placed the order';
COMMENT ON COLUMN orders.manager_id IS 'Менеджер магазина; NULL для онлайн-заказов / Store manager, NULL for online orders';
COMMENT ON COLUMN orders.channel IS 'Канал продаж: online — сайт и приложение, store — офлайн-магазин / Sales channel';
COMMENT ON COLUMN orders.status IS 'Статус: new — оформлен, paid — оплачен, shipped — отгружен, delivered — доставлен, cancelled — отменён / Order status';
COMMENT ON COLUMN orders.created_at IS 'Дата и время оформления заказа (не оплаты) / Order placement timestamp (not payment)';
COMMENT ON COLUMN orders.discount_amount IS 'Скидка по заказу в тенге / Order discount, KZT';
COMMENT ON COLUMN orders.total_amount IS 'Сумма заказа в тенге после скидки, без учёта возвратов / Order total after discount, KZT, returns not deducted';

CREATE TABLE order_items (
    order_id   integer NOT NULL REFERENCES orders (id),
    product_id integer NOT NULL REFERENCES products (id),
    quantity   integer NOT NULL CHECK (quantity > 0),
    unit_price numeric(12, 2) NOT NULL CHECK (unit_price > 0),
    PRIMARY KEY (order_id, product_id)
);
COMMENT ON TABLE order_items IS 'Позиции заказов / Order line items';
COMMENT ON COLUMN order_items.order_id IS 'Заказ / Order';
COMMENT ON COLUMN order_items.product_id IS 'Товар / Product';
COMMENT ON COLUMN order_items.quantity IS 'Количество проданных единиц / Units sold';
COMMENT ON COLUMN order_items.unit_price IS 'Цена единицы на момент продажи в тенге / Unit price at time of sale, KZT';

CREATE TABLE payments (
    id      integer PRIMARY KEY,
    order_id integer NOT NULL REFERENCES orders (id),
    paid_at timestamptz NOT NULL,
    amount  numeric(14, 2) NOT NULL CHECK (amount > 0),
    method  text NOT NULL CHECK (method IN ('card', 'kaspi_qr', 'cash', 'bank_transfer'))
);
COMMENT ON TABLE payments IS 'Платежи по заказам; у b2b-заказа может быть несколько платежей / Order payments, b2b orders may have several';
COMMENT ON COLUMN payments.id IS 'Идентификатор платежа / Payment ID';
COMMENT ON COLUMN payments.order_id IS 'Оплачиваемый заказ / Paid order';
COMMENT ON COLUMN payments.paid_at IS 'Дата и время поступления оплаты / Payment timestamp';
COMMENT ON COLUMN payments.amount IS 'Сумма платежа в тенге / Payment amount, KZT';
COMMENT ON COLUMN payments.method IS 'Способ оплаты: card, kaspi_qr, cash, bank_transfer / Payment method';

CREATE TABLE returns (
    id          integer PRIMARY KEY,
    order_id    integer NOT NULL REFERENCES orders (id),
    returned_at timestamptz NOT NULL,
    amount      numeric(14, 2) NOT NULL CHECK (amount > 0),
    reason      text NOT NULL CHECK (reason IN ('defect', 'not_as_described', 'changed_mind', 'late_delivery'))
);
COMMENT ON TABLE returns IS 'Возвраты по доставленным заказам / Returns of delivered orders';
COMMENT ON COLUMN returns.id IS 'Идентификатор возврата / Return ID';
COMMENT ON COLUMN returns.order_id IS 'Заказ, по которому оформлен возврат / Returned order';
COMMENT ON COLUMN returns.returned_at IS 'Дата и время возврата / Return timestamp';
COMMENT ON COLUMN returns.amount IS 'Сумма возврата в тенге / Refund amount, KZT';
COMMENT ON COLUMN returns.reason IS 'Причина: defect — брак, not_as_described — не соответствует описанию, changed_mind — передумал, late_delivery — опоздание доставки / Return reason';

CREATE TABLE fiscal_calendar (
    date             date PRIMARY KEY,
    calendar_year    smallint NOT NULL,
    calendar_quarter smallint NOT NULL CHECK (calendar_quarter BETWEEN 1 AND 4),
    fiscal_year      smallint NOT NULL,
    fiscal_quarter   smallint NOT NULL CHECK (fiscal_quarter BETWEEN 1 AND 4)
);
COMMENT ON TABLE fiscal_calendar IS 'Календарь компании: финансовый год начинается 1 апреля / Company calendar, fiscal year starts on April 1';
COMMENT ON COLUMN fiscal_calendar.date IS 'Дата / Date';
COMMENT ON COLUMN fiscal_calendar.calendar_year IS 'Календарный год / Calendar year';
COMMENT ON COLUMN fiscal_calendar.calendar_quarter IS 'Календарный квартал (Q1 = январь–март) / Calendar quarter';
COMMENT ON COLUMN fiscal_calendar.fiscal_year IS 'Финансовый год, названный по году начала: FY2025 = 01.04.2025–31.03.2026 / Fiscal year named by its start year';
COMMENT ON COLUMN fiscal_calendar.fiscal_quarter IS 'Финансовый квартал (FQ1 = апрель–июнь) / Fiscal quarter';

-- Индексы под типичные аналитические запросы
CREATE INDEX orders_created_at_idx ON orders (created_at);
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
CREATE INDEX orders_manager_id_idx ON orders (manager_id);
CREATE INDEX order_items_product_id_idx ON order_items (product_id);
CREATE INDEX payments_order_id_idx ON payments (order_id);
CREATE INDEX payments_paid_at_idx ON payments (paid_at);
CREATE INDEX returns_order_id_idx ON returns (order_id);
CREATE INDEX customers_city_id_idx ON customers (city_id);
CREATE INDEX cities_region_id_idx ON cities (region_id);
