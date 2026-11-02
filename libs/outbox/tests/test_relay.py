"""Outbox и relay на настоящем PostgreSQL: блокировки и транзакции не проверить на подделке."""

import json
from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from contracts import OrderLine, ReserveStock
from outbox import OutboxRelay, OutboxWriter, define_outbox_table

pytestmark = pytest.mark.integration

metadata = MetaData()
outbox_table = define_outbox_table(metadata)


class RecordingPublisher:
    def __init__(self, fail: bool = False) -> None:
        self.sent: list[tuple[str, str, dict[str, object]]] = []
        self.fail = fail

    async def publish(self, topic: str, key: str, value: bytes) -> None:
        if self.fail:
            raise ConnectionError("Kafka недоступна")
        self.sent.append((topic, key, json.loads(value)))


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


def make_command() -> ReserveStock:
    return ReserveStock(order_id=uuid4(), lines=(OrderLine(sku="iphone-17-256", quantity=1),))


async def put(factory: async_sessionmaker[AsyncSession], command: ReserveStock) -> None:
    async with factory.begin() as session:
        await OutboxWriter(session, outbox_table).put("inventory.commands", command)


async def unpublished_count(factory: async_sessionmaker[AsyncSession]) -> int:
    async with factory() as session:
        query = (
            select(func.count())
            .select_from(outbox_table)
            .where(outbox_table.c.published_at.is_(None))
        )
        return int(await session.scalar(query) or 0)


async def test_relay_publishes_in_order_and_marks_published(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    first, second = make_command(), make_command()
    await put(session_factory, first)
    await put(session_factory, second)
    publisher = RecordingPublisher()

    published = await OutboxRelay(session_factory, outbox_table, publisher).publish_batch()

    assert published == 2
    assert [(topic, key) for topic, key, _ in publisher.sent] == [
        ("inventory.commands", str(first.order_id)),
        ("inventory.commands", str(second.order_id)),
    ]
    assert ReserveStock.model_validate(publisher.sent[0][2]) == first
    assert await unpublished_count(session_factory) == 0


async def test_rolled_back_transaction_leaves_nothing_to_publish(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        await OutboxWriter(session, outbox_table).put("inventory.commands", make_command())
        await session.rollback()

    assert await unpublished_count(session_factory) == 0


async def test_failed_publish_keeps_messages_for_next_attempt(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await put(session_factory, make_command())

    with pytest.raises(ConnectionError):
        await OutboxRelay(
            session_factory, outbox_table, RecordingPublisher(fail=True)
        ).publish_batch()

    assert await unpublished_count(session_factory) == 1
    publisher = RecordingPublisher()
    assert await OutboxRelay(session_factory, outbox_table, publisher).publish_batch() == 1
