"""Фоновый процесс order: принимает ответы inventory и antifraud и публикует outbox.

Запуск: python -m order.worker
"""

import asyncio
import logging
from typing import Annotated

from pydantic import Field, TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from contracts import AntifraudEvent, InventoryEvent
from contracts.topics import ANTIFRAUD_EVENTS, INVENTORY_EVENTS
from messaging import IdempotentConsumer, KafkaPublisher, OutboxRelay, OutboxWriter
from order.config import Settings
from order.service.saga import SagaService
from order.storage.db import create_engine, create_session_factory
from order.storage.order_repository import PostgresOrderRepository
from order.storage.tables import outbox, processed_messages

# Ответы обоих участников саги разбираются по полю type.
saga_events: TypeAdapter[InventoryEvent | AntifraudEvent] = TypeAdapter(
    Annotated[InventoryEvent | AntifraudEvent, Field(discriminator="type")]
)


async def handle_event(session: AsyncSession, value: bytes) -> None:
    event = saga_events.validate_json(value)
    saga = SagaService(PostgresOrderRepository(session), OutboxWriter(session, outbox))
    await saga.on_event(event)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    engine = create_engine(str(settings.database_url))
    session_factory = create_session_factory(engine)
    publisher = KafkaPublisher(settings.kafka_bootstrap_servers)
    consumer = IdempotentConsumer(session_factory, processed_messages, handle_event)
    await publisher.start()
    try:
        await asyncio.gather(
            consumer.run(
                [INVENTORY_EVENTS, ANTIFRAUD_EVENTS], "order", settings.kafka_bootstrap_servers
            ),
            OutboxRelay(session_factory, outbox, publisher).run(),
        )
    finally:
        await publisher.stop()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
