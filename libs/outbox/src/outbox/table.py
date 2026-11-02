from sqlalchemy import BigInteger, Column, DateTime, MetaData, Table, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB


def define_outbox_table(metadata: MetaData) -> Table:
    """Добавляет таблицу outbox в схему сервиса. Миграцию сервис делает сам."""
    return Table(
        "outbox",
        metadata,
        # Порядковый номер: relay публикует сообщения в том порядке, в каком их записали.
        Column("id", BigInteger, primary_key=True, autoincrement=True),
        Column("message_id", Uuid, nullable=False, unique=True),
        Column("topic", Text, nullable=False),
        Column("key", Text, nullable=False),
        Column("payload", JSONB, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("published_at", DateTime(timezone=True)),
    )
