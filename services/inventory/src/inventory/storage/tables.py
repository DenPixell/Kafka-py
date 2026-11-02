"""Схема БД сервиса inventory. Миграции в migrations/ строятся по этому описанию."""

from sqlalchemy import (
    ARRAY,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
)

from messaging import define_outbox_table, define_processed_messages_table

metadata = MetaData(
    naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
    }
)

categories = Table(
    "categories",
    metadata,
    Column("slug", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("position", Integer, nullable=False),
)

products = Table(
    "products",
    metadata,
    Column("slug", Text, primary_key=True),
    Column("category_slug", Text, ForeignKey("categories.slug"), nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text, nullable=False, server_default=""),
    Column("position", Integer, nullable=False),
)

# Палитра модели. Фото лежат списком в порядке показа в карусели:
# порядок важен, а отдельно от цвета они не используются.
product_colors = Table(
    "product_colors",
    metadata,
    Column("product_slug", Text, ForeignKey("products.slug"), primary_key=True),
    Column("slug", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("hex", String(7), nullable=False),
    Column("position", Integer, nullable=False),
    Column("images", ARRAY(Text), nullable=False),
    CheckConstraint("hex ~ '^#[0-9a-f]{6}$'", name="hex_format"),
)

product_variants = Table(
    "product_variants",
    metadata,
    Column("sku", Text, primary_key=True),
    Column("product_slug", Text, ForeignKey("products.slug"), nullable=False),
    Column("storage_gb", Integer, nullable=False),
    Column("screen_inch", Numeric(3, 1), nullable=False),
    Column("color_slug", Text, nullable=False),
    # Деньги в копейках: целое число, без ошибок округления.
    Column("price_kopecks", BigInteger, nullable=False),
    Column("note", Text),
    UniqueConstraint("product_slug", "storage_gb", "screen_inch", "color_slug"),
    # Цвет должен быть из палитры именно этой модели.
    ForeignKeyConstraint(
        ["product_slug", "color_slug"],
        ["product_colors.product_slug", "product_colors.slug"],
        # Имя по шаблону совпало бы с ключом product_slug → products.
        name="fk_product_variants_color",
    ),
    CheckConstraint("storage_gb > 0", name="storage_positive"),
    CheckConstraint("screen_inch > 0", name="screen_positive"),
    CheckConstraint("price_kopecks > 0", name="price_positive"),
)

stock = Table(
    "stock",
    metadata,
    Column("sku", Text, ForeignKey("product_variants.sku"), primary_key=True),
    Column("quantity", Integer, nullable=False),
    # Сколько штук отложено под заказы, которые ещё проходят сагу.
    Column("reserved", Integer, nullable=False, server_default="0"),
    CheckConstraint("quantity >= 0", name="quantity_non_negative"),
    CheckConstraint("reserved >= 0 AND reserved <= quantity", name="reserved_within_quantity"),
)

# Что отложено под какой заказ: по этим строкам снимается резерв при компенсации.
reservations = Table(
    "reservations",
    metadata,
    Column("order_id", Uuid, primary_key=True),
    Column("sku", Text, ForeignKey("product_variants.sku"), primary_key=True),
    Column("quantity", Integer, nullable=False),
    # Цена на момент резерва: если каталог подорожает, сумма заказа не изменится.
    Column("unit_price_kopecks", BigInteger, nullable=False),
    Column("released_at", DateTime(timezone=True)),
    CheckConstraint("quantity > 0", name="quantity_positive"),
)

outbox = define_outbox_table(metadata)
processed_messages = define_processed_messages_table(metadata)
