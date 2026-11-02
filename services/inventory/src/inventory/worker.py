"""Фоновый процесс inventory: принимает команды саги и публикует ответы.

Запуск: python -m inventory.worker
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from contracts import inventory_commands
from contracts.topics import INVENTORY_COMMANDS
from inventory.config import Settings
from inventory.service.reservations import ReservationService
from inventory.storage.db import create_engine, create_session_factory
from inventory.storage.stock_repository import PostgresStockRepository
from inventory.storage.tables import outbox, processed_messages
from messaging import IdempotentConsumer, KafkaPublisher, OutboxRelay, OutboxWriter


async def handle_command(session: AsyncSession, value: bytes) -> None:
    command = inventory_commands.validate_json(value)
    service = ReservationService(PostgresStockRepository(session), OutboxWriter(session, outbox))
    await service.handle(command)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    engine = create_engine(str(settings.database_url))
    session_factory = create_session_factory(engine)
    publisher = KafkaPublisher(settings.kafka_bootstrap_servers)
    consumer = IdempotentConsumer(session_factory, processed_messages, handle_command)
    await publisher.start()
    try:
        await asyncio.gather(
            consumer.run(INVENTORY_COMMANDS, "inventory", settings.kafka_bootstrap_servers),
            OutboxRelay(session_factory, outbox, publisher).run(),
        )
    finally:
        await publisher.stop()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
