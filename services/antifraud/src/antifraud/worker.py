"""Процесс antifraud: проверяет заказы из Kafka и публикует решения.

Запуск: python -m antifraud.worker
"""

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from antifraud.config import Settings
from antifraud.service.checks import FraudCheckService
from antifraud.storage.check_history import PostgresCheckHistory
from antifraud.storage.db import create_engine, create_session_factory
from antifraud.storage.tables import outbox, processed_messages
from contracts import antifraud_commands
from contracts.topics import ANTIFRAUD_COMMANDS
from messaging import OutboxWriter, run_worker


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    rules = settings.rules()

    async def handle_command(session: AsyncSession, value: bytes) -> None:
        service = FraudCheckService(
            PostgresCheckHistory(session),
            OutboxWriter(session, outbox),
            rules,
            settings.reject_threshold,
            settings.frequent_orders_window,
        )
        await service.handle(antifraud_commands.validate_json(value))

    engine = create_engine(str(settings.database_url))
    try:
        await run_worker(
            session_factory=create_session_factory(engine),
            outbox_table=outbox,
            processed_table=processed_messages,
            handler=handle_command,
            topics=[ANTIFRAUD_COMMANDS],
            group_id="antifraud",
            bootstrap_servers=settings.kafka_bootstrap_servers,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
