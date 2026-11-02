"""Идемпотентный консьюмер Kafka.

Kafka и relay гарантируют доставку at-least-once: одно сообщение может прийти
дважды. Поэтому id обработанного сообщения сохраняется в той же транзакции,
что и результат обработки, а повтор просто пропускается.
"""

import json
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from sqlalchemy import Column, DateTime, MetaData, Table, Uuid, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Обработчик получает сессию с уже открытой транзакцией и тело сообщения.
Handler = Callable[[AsyncSession, bytes], Awaitable[None]]


def define_processed_messages_table(metadata: MetaData) -> Table:
    return Table(
        "processed_messages",
        metadata,
        Column("message_id", Uuid, primary_key=True),
        Column("processed_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    )


class IdempotentConsumer:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        processed_table: Table,
        handler: Handler,
    ) -> None:
        self._session_factory = session_factory
        self._processed = processed_table
        self._handler = handler

    async def handle(self, value: bytes) -> bool:
        """Обрабатывает сообщение. Возвращает False, если оно уже было обработано."""
        message_id = UUID(json.loads(value)["message_id"])
        async with self._session_factory.begin() as session:
            inserted = await session.execute(
                insert(self._processed)
                .values(message_id=message_id)
                .on_conflict_do_nothing()
                .returning(self._processed.c.message_id)
            )
            if inserted.first() is None:
                logger.info("Сообщение %s уже обработано, пропускаю", message_id)
                return False
            # Если обработчик упадёт, откатится и отметка об обработке:
            # сообщение обработается заново.
            await self._handler(session, value)
        return True

    async def run(self, topics: list[str], group_id: str, bootstrap_servers: str) -> None:
        consumer = AIOKafkaConsumer(
            *topics,
            group_id=group_id,
            bootstrap_servers=bootstrap_servers,
            # Оффсет коммитим сами и только после коммита в БД.
            enable_auto_commit=False,
            auto_offset_reset="earliest",
        )
        await consumer.start()
        try:
            async for record in consumer:
                await self.handle(record.value)
                await consumer.commit()
        finally:
            await consumer.stop()
