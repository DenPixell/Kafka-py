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
from messaging import OutboxWriter, run_worker
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
    try:
        await run_worker(
            session_factory=create_session_factory(engine),
            outbox_table=outbox,
            processed_table=processed_messages,
            handler=handle_event,
            topics=[INVENTORY_EVENTS, ANTIFRAUD_EVENTS],
            group_id="order",
            bootstrap_servers=settings.kafka_bootstrap_servers,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
