"""Схема БД сервиса antifraud. Миграции в migrations/ строятся по этому описанию."""

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
)

from messaging import define_outbox_table, define_processed_messages_table

metadata = MetaData(
    naming_convention={
        "pk": "pk_%(table_name)s",
        "ix": "ix_%(table_name)s_%(column_0_name)s",
    }
)

checks = Table(
    "checks",
    metadata,
    Column("order_id", Uuid, primary_key=True),
    Column("user_id", Text, nullable=False),
    Column("total_kopecks", BigInteger, nullable=False),
    Column("delivery_country", String(2), nullable=False),
    Column("checked_at", DateTime(timezone=True), nullable=False),
    Column("score", Integer, nullable=False),
    Column("reasons", ARRAY(Text), nullable=False),
    Column("approved", Boolean, nullable=False),
    # История покупателя всегда читается по user_id в окне времени.
    Index(None, "user_id", "checked_at"),
)

outbox = define_outbox_table(metadata)
processed_messages = define_processed_messages_table(metadata)
