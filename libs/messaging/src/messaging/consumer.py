"""Идемпотентный консьюмер Kafka с повторами и DLQ.

Kafka и relay гарантируют доставку at-least-once: одно сообщение может прийти
дважды. Поэтому id обработанного сообщения сохраняется в той же транзакции,
что и результат обработки, а повтор просто пропускается.

Если обработка падает, она повторяется с нарастающей паузой. Если не помогло,
сообщение уходит в топик <топик>.dlq, а консьюмер идёт дальше: одно «ядовитое»
сообщение не должно останавливать всю партицию.
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from uuid import UUID

from aiokafka import AIOKafkaConsumer
from sqlalchemy import Column, DateTime, MetaData, Table, Uuid, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from messaging.publisher import Publisher

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


class PoisonMessageError(ValueError):
    """Сообщение нельзя даже разобрать. Повтор не поможет."""


class IdempotentConsumer:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        processed_table: Table,
        handler: Handler,
        dead_letters: Publisher,
        max_attempts: int = 3,
        retry_delay: float = 0.5,
    ) -> None:
        self._session_factory = session_factory
        self._processed = processed_table
        self._handler = handler
        self._dead_letters = dead_letters
        self._max_attempts = max_attempts
        self._retry_delay = retry_delay

    async def consume(self, topic: str, key: bytes | None, value: bytes) -> None:
        """Обрабатывает сообщение с повторами. Если не вышло, кладёт его в DLQ."""
        for attempt in range(1, self._max_attempts + 1):
            try:
                await self.handle(value)
                return
            except ValueError as error:
                # Плохие данные (не тот JSON, не та схема): повтор даст ту же ошибку.
                logger.error("Сообщение из %s не разобрать: %s", topic, error)
                await self._to_dead_letters(topic, key, value, error)
                return
            except Exception as error:
                if attempt == self._max_attempts:
                    logger.exception("Сообщение из %s не обработано за %d попыток", topic, attempt)
                    await self._to_dead_letters(topic, key, value, error)
                    return
                delay = self._retry_delay * 2 ** (attempt - 1)
                logger.warning(
                    "Попытка %d для сообщения из %s не удалась (%s), повтор через %.1f с",
                    attempt,
                    topic,
                    error,
                    delay,
                )
                await asyncio.sleep(delay)

    async def handle(self, value: bytes) -> bool:
        """Обрабатывает сообщение. Возвращает False, если оно уже было обработано."""
        try:
            message_id = UUID(json.loads(value)["message_id"])
        except (ValueError, KeyError, TypeError) as error:
            raise PoisonMessageError(f"нет корректного message_id: {error!r}") from error
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
                await self.consume(record.topic, record.key, record.value)
                await consumer.commit()
        finally:
            # При остановке консьюмер сразу уходит из группы, и Kafka без ожидания
            # таймаута отдаёт его партиции другим экземплярам.
            await consumer.stop()

    async def _to_dead_letters(
        self, topic: str, key: bytes | None, value: bytes, error: Exception
    ) -> None:
        # Исходное сообщение без изменений плюс заголовки с причиной: его можно
        # разобрать вручную и, исправив ошибку, отправить в исходный топик заново.
        await self._dead_letters.publish(
            f"{topic}.dlq",
            key.decode() if key else "",
            value,
            headers=[
                ("error.type", type(error).__name__.encode()),
                ("error.message", str(error).encode()[:1000]),
            ],
        )
