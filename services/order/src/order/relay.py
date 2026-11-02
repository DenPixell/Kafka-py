"""Отдельный процесс, который переносит сообщения из outbox в Kafka.

Запуск: python -m order.relay
"""

import asyncio
import logging

from order.config import Settings
from order.storage.db import create_engine, create_session_factory
from order.storage.tables import outbox
from outbox import KafkaPublisher, OutboxRelay


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = Settings()
    engine = create_engine(str(settings.database_url))
    publisher = KafkaPublisher(settings.kafka_bootstrap_servers)
    await publisher.start()
    try:
        await OutboxRelay(create_session_factory(engine), outbox, publisher).run()
    finally:
        await publisher.stop()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
