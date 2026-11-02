"""Схема БД сервиса inventory. Миграции в migrations/ строятся по этому описанию."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    Table,
    Text,
    UniqueConstraint,
)

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
    Column("position", Integer, nullable=False),
)

product_variants = Table(
    "product_variants",
    metadata,
    Column("sku", Text, primary_key=True),
    Column("product_slug", Text, ForeignKey("products.slug"), nullable=False),
    Column("storage_gb", Integer, nullable=False),
    Column("screen_inch", Numeric(3, 1), nullable=False),
    # Деньги в копейках: целое число, без ошибок округления.
    Column("price_kopecks", BigInteger, nullable=False),
    Column("note", Text),
    UniqueConstraint("product_slug", "storage_gb", "screen_inch"),
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
