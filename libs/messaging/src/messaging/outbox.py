"""Transactional Outbox: сообщения пишутся в БД в одной транзакции с данными."""

from sqlalchemy import BigInteger, Column, DateTime, MetaData, Table, Text, Uuid, func, insert
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from contracts import Message


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


class OutboxWriter:
    """Кладёт сообщение в outbox в текущей транзакции.

    Сообщение попадёт в Kafka, только если транзакция с бизнес-изменениями
    закоммитится. Откат транзакции отменяет и сообщение.
    """

    def __init__(self, session: AsyncSession, table: Table) -> None:
        self._session = session
        self._table = table

    async def put(self, topic: str, message: Message) -> None:
        await self._session.execute(
            insert(self._table).values(
                message_id=message.message_id,
                topic=topic,
                key=str(message.order_id),
                payload=message.model_dump(mode="json"),
            )
        )
