"""Схема БД сервиса order. Миграции в migrations/ строятся по этому описанию."""

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    Uuid,
)

from messaging import define_outbox_table, define_processed_messages_table
from order.domain.order import CancelReason, OrderStatus

metadata = MetaData(
    naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "ix": "ix_%(table_name)s_%(column_0_name)s",
    }
)


def _one_of(column: str, values: type[OrderStatus] | type[CancelReason]) -> str:
    listed = ", ".join(f"'{v.value}'" for v in values)
    return f"{column} IN ({listed})"


orders = Table(
    "orders",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("user_id", Text, nullable=False, index=True),
    # Статусы — закрытый набор из машины состояний, поэтому CHECK, а не справочник.
    Column("status", Text, nullable=False),
    Column("delivery_country", String(2), nullable=False),
    Column("total_kopecks", BigInteger),
    Column("cancel_reason", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(_one_of("status", OrderStatus), name="status_known"),
    CheckConstraint(
        "cancel_reason IS NULL OR " + _one_of("cancel_reason", CancelReason),
        name="cancel_reason_known",
    ),
    CheckConstraint("total_kopecks IS NULL OR total_kopecks > 0", name="total_positive"),
)

order_items = Table(
    "order_items",
    metadata,
    Column("order_id", Uuid, ForeignKey("orders.id"), primary_key=True),
    Column("sku", Text, primary_key=True),
    Column("quantity", Integer, nullable=False),
    CheckConstraint("quantity > 0", name="quantity_positive"),
)

outbox = define_outbox_table(metadata)
processed_messages = define_processed_messages_table(metadata)
