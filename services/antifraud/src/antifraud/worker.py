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
from messaging import IdempotentConsumer, KafkaPublisher, OutboxRelay, OutboxWriter


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
    session_factory = create_session_factory(engine)
    publisher = KafkaPublisher(settings.kafka_bootstrap_servers)
    consumer = IdempotentConsumer(session_factory, processed_messages, handle_command)
    await publisher.start()
    try:
        await asyncio.gather(
            consumer.run([ANTIFRAUD_COMMANDS], "antifraud", settings.kafka_bootstrap_servers),
            OutboxRelay(session_factory, outbox, publisher).run(),
        )
    finally:
        await publisher.stop()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
