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
from messaging import OutboxWriter, run_worker


async def handle_command(session: AsyncSession, value: bytes) -> None:
    command = inventory_commands.validate_json(value)
    service = ReservationService(PostgresStockRepository(session), OutboxWriter(session, outbox))
    await service.handle(command)


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    engine = create_engine(str(settings.database_url))
    try:
        await run_worker(
            session_factory=create_session_factory(engine),
            outbox_table=outbox,
            processed_table=processed_messages,
            handler=handle_command,
            topics=[INVENTORY_COMMANDS],
            group_id="inventory",
            bootstrap_servers=settings.kafka_bootstrap_servers,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
