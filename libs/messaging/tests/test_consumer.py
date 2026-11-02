"""Консьюмер на настоящем PostgreSQL: идемпотентность, повторы и DLQ."""

from collections.abc import AsyncIterator, Iterator
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import MetaData, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from contracts import ReleaseStock
from messaging import Headers, IdempotentConsumer, define_processed_messages_table

pytestmark = pytest.mark.integration

metadata = MetaData()
processed = define_processed_messages_table(metadata)
TOPIC = "inventory.commands"


class RecordingHandler:
    def __init__(self, fail_times: int = 0, error: Exception | None = None) -> None:
        self.calls: list[bytes] = []
        self.fail_times = fail_times
        self.error = error or RuntimeError("БД недоступна")

    async def __call__(self, session: AsyncSession, value: bytes) -> None:
        self.calls.append(value)
        if len(self.calls) <= self.fail_times:
            raise self.error


class DeadLetters:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, bytes, dict[str, bytes]]] = []

    async def publish(
        self, topic: str, key: str, value: bytes, headers: Headers | None = None
    ) -> None:
        self.sent.append((topic, key, value, dict(headers or [])))


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


@pytest.fixture
def dead_letters() -> DeadLetters:
    return DeadLetters()


def make_consumer(
    factory: async_sessionmaker[AsyncSession], handler: RecordingHandler, dlq: DeadLetters
) -> IdempotentConsumer:
    return IdempotentConsumer(factory, processed, handler, dlq, max_attempts=3, retry_delay=0)


def message() -> bytes:
    return ReleaseStock(order_id=uuid4()).model_dump_json().encode()


async def test_duplicate_is_handled_once(
    session_factory: async_sessionmaker[AsyncSession], dead_letters: DeadLetters
) -> None:
    handler = RecordingHandler()
    consumer = make_consumer(session_factory, handler, dead_letters)
    value = message()

    first = await consumer.handle(value)
    second = await consumer.handle(value)

    assert (first, second) == (True, False)
    assert handler.calls == [value]


async def test_failed_handling_rolls_back_processed_mark(
    session_factory: async_sessionmaker[AsyncSession], dead_letters: DeadLetters
) -> None:
    handler = RecordingHandler(fail_times=1)
    consumer = make_consumer(session_factory, handler, dead_letters)
    value = message()

    with pytest.raises(RuntimeError):
        await consumer.handle(value)
    retried = await consumer.handle(value)

    assert retried is True
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(processed)) == 1


async def test_transient_error_is_retried(
    session_factory: async_sessionmaker[AsyncSession], dead_letters: DeadLetters
) -> None:
    handler = RecordingHandler(fail_times=2)

    await make_consumer(session_factory, handler, dead_letters).consume(TOPIC, b"k", message())

    assert len(handler.calls) == 3
    assert dead_letters.sent == []


async def test_persistent_error_goes_to_dlq_after_all_attempts(
    session_factory: async_sessionmaker[AsyncSession], dead_letters: DeadLetters
) -> None:
    handler = RecordingHandler(fail_times=10)
    value = message()

    await make_consumer(session_factory, handler, dead_letters).consume(TOPIC, b"order-1", value)

    assert len(handler.calls) == 3
    [(topic, key, sent, headers)] = dead_letters.sent
    assert (topic, key, sent) == ("inventory.commands.dlq", "order-1", value)
    assert headers["error.type"] == b"RuntimeError"


async def test_broken_json_goes_to_dlq_without_retries(
    session_factory: async_sessionmaker[AsyncSession], dead_letters: DeadLetters
) -> None:
    handler = RecordingHandler()

    await make_consumer(session_factory, handler, dead_letters).consume(TOPIC, None, b"not json")

    assert handler.calls == []
    [(_, _, _, headers)] = dead_letters.sent
    assert headers["error.type"] == b"PoisonMessageError"


async def test_invalid_schema_goes_to_dlq_without_retries(
    session_factory: async_sessionmaker[AsyncSession], dead_letters: DeadLetters
) -> None:
    try:
        ReleaseStock.model_validate({})
    except ValidationError as error:
        schema_error = error
    handler = RecordingHandler(fail_times=10, error=schema_error)

    await make_consumer(session_factory, handler, dead_letters).consume(TOPIC, None, message())

    assert len(handler.calls) == 1
    [(_, _, _, headers)] = dead_letters.sent
    assert headers["error.type"] == b"ValidationError"
