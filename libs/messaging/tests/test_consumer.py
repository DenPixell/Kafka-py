"""Идемпотентность консьюмера на настоящем PostgreSQL."""

from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from contracts import ReleaseStock
from messaging import IdempotentConsumer, define_processed_messages_table

pytestmark = pytest.mark.integration

metadata = MetaData()
processed = define_processed_messages_table(metadata)


class RecordingHandler:
    def __init__(self, fail_times: int = 0) -> None:
        self.calls: list[bytes] = []
        self.fail_times = fail_times

    async def __call__(self, session: AsyncSession, value: bytes) -> None:
        self.calls.append(value)
        if len(self.calls) <= self.fail_times:
            raise RuntimeError("сбой обработки")


@pytest.fixture(scope="module")
def database_url() -> Iterator[str]:
    with PostgresContainer("postgres:17.11-alpine", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture
async def session_factory(database_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(metadata.drop_all)
        await connection.run_sync(metadata.create_all)
    yield async_sessionmaker(engine)
    await engine.dispose()


def message() -> bytes:
    return ReleaseStock(order_id=uuid4()).model_dump_json().encode()


async def test_duplicate_is_handled_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    handler = RecordingHandler()
    consumer = IdempotentConsumer(session_factory, processed, handler)
    value = message()

    first = await consumer.handle(value)
    second = await consumer.handle(value)

    assert (first, second) == (True, False)
    assert handler.calls == [value]


async def test_failed_handling_is_retried(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    handler = RecordingHandler(fail_times=1)
    consumer = IdempotentConsumer(session_factory, processed, handler)
    value = message()

    with pytest.raises(RuntimeError):
        await consumer.handle(value)
    retried = await consumer.handle(value)

    assert retried is True
    assert len(handler.calls) == 2
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(processed)) == 1
