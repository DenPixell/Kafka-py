import asyncio
import json
import logging

from sqlalchemy import Table, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from messaging.publisher import Publisher

logger = logging.getLogger(__name__)


class OutboxRelay:
    """Переносит сообщения из outbox в Kafka.

    Гарантия — at-least-once: если процесс упадёт после отправки, но до отметки
    published_at, сообщение уйдёт ещё раз. Поэтому консьюмеры идемпотентны.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        table: Table,
        publisher: Publisher,
        batch_size: int = 100,
    ) -> None:
        self._session_factory = session_factory
        self._table = table
        self._publisher = publisher
        self._batch_size = batch_size

    async def publish_batch(self) -> int:
        """Публикует одну пачку и возвращает, сколько сообщений отправлено."""
        table = self._table
        async with self._session_factory.begin() as session:
            # SKIP LOCKED: несколько экземпляров relay не возьмут одни и те же строки.
            rows = (
                await session.execute(
                    select(table.c.id, table.c.topic, table.c.key, table.c.payload)
                    .where(table.c.published_at.is_(None))
                    .order_by(table.c.id)
                    .limit(self._batch_size)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for row in rows:
                await self._publisher.publish(row.topic, row.key, json.dumps(row.payload).encode())
            if rows:
                await session.execute(
                    update(table)
                    .where(table.c.id.in_([row.id for row in rows]))
                    .values(published_at=func.now())
                )
        return len(rows)

    async def run(self, poll_interval: float = 0.5) -> None:
        while True:
            try:
                published = await self.publish_batch()
            except Exception:
                logger.exception("Не удалось опубликовать сообщения из outbox, повторю позже")
                published = 0
            if published:
                logger.info("Опубликовано сообщений: %d", published)
            else:
                await asyncio.sleep(poll_interval)
