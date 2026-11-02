from sqlalchemy import Table, insert
from sqlalchemy.ext.asyncio import AsyncSession

from contracts import Message


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
