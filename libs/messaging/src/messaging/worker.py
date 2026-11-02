"""Запуск фонового процесса сервиса: консьюмер команд или событий плюс relay outbox."""

import asyncio
import logging
import signal
from collections.abc import Coroutine
from typing import Any

from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from messaging.consumer import Handler, IdempotentConsumer
from messaging.publisher import KafkaPublisher
from messaging.relay import OutboxRelay

logger = logging.getLogger(__name__)


async def run_until_stopped(*jobs: Coroutine[Any, Any, None]) -> None:
    """Выполняет задачи, пока не придёт SIGTERM или SIGINT, либо пока одна не упадёт.

    По сигналу задачи отменяются, и их блоки finally успевают закрыть соединения:
    консьюмер выходит из группы, транзакция в БД откатывается, оффсет не коммитится.
    """
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    tasks = [asyncio.create_task(job) for job in jobs]
    stopper = asyncio.create_task(stop.wait())
    done, _ = await asyncio.wait([*tasks, stopper], return_when=asyncio.FIRST_COMPLETED)
    if stopper in done:
        logger.info("Получен сигнал остановки, завершаю работу")
    for task in [*tasks, stopper]:
        task.cancel()
    await asyncio.gather(*tasks, stopper, return_exceptions=True)

    # Если остановились из-за упавшей задачи, а не по сигналу, — сообщаем об ошибке.
    for task in done:
        if task is stopper or task.cancelled():
            continue
        error = task.exception()
        if error is not None:
            raise error


async def run_worker(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    outbox_table: Table,
    processed_table: Table,
    handler: Handler,
    topics: list[str],
    group_id: str,
    bootstrap_servers: str,
) -> None:
    publisher = KafkaPublisher(bootstrap_servers)
    await publisher.start()
    consumer = IdempotentConsumer(session_factory, processed_table, handler, dead_letters=publisher)
    relay = OutboxRelay(session_factory, outbox_table, publisher)
    try:
        await run_until_stopped(
            consumer.run(topics, group_id, bootstrap_servers),
            relay.run(),
        )
    finally:
        await publisher.stop()
