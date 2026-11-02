"""История проверок на настоящем PostgreSQL."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer

from antifraud.domain.check import FraudCheck
from antifraud.domain.rules import Verdict
from antifraud.storage.check_history import PostgresCheckHistory
from antifraud.storage.db import create_engine, create_session_factory

pytestmark = pytest.mark.integration

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def database_url() -> Iterator[str]:
    with PostgresContainer("postgres:17.11-alpine", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        config = Config(ALEMBIC_INI)
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        yield url


@pytest.fixture
async def session_factory(database_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(database_url)
    yield create_session_factory(engine)
    await engine.dispose()


def make_check(user: str, country: str, at: datetime, approved: bool = True) -> FraudCheck:
    return FraudCheck(
        order_id=uuid4(),
        user_id=user,
        total_kopecks=8_000_000,
        delivery_country=country,
        checked_at=at,
        verdict=Verdict(
            score=0 if approved else 90, reasons=() if approved else ("x",), approved=approved
        ),
    )


async def test_history_round_trip_and_queries(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    user = f"user-{uuid4()}"
    old = make_check(user, "RU", NOW - timedelta(hours=1))
    recent = make_check(user, "KZ", NOW - timedelta(minutes=5))
    rejected = make_check(user, "AM", NOW - timedelta(minutes=1), approved=False)
    async with session_factory.begin() as session:
        history = PostgresCheckHistory(session)
        for check in (old, recent, rejected):
            await history.add(check)

    async with session_factory() as session:
        history = PostgresCheckHistory(session)
        assert await history.find(rejected.order_id) == rejected
        assert await history.count_since(user, NOW - timedelta(minutes=10)) == 2
        assert await history.approved_countries(user) == frozenset({"RU", "KZ"})


async def test_user_lock_serializes_checks(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Вторая транзакция ждёт, пока первая не закоммитит свою проверку, и видит её."""
    user = f"user-{uuid4()}"
    first_locked = asyncio.Event()
    seen_by_second: list[int] = []

    async def first() -> None:
        async with session_factory.begin() as session:
            history = PostgresCheckHistory(session)
            await history.lock_user(user)
            first_locked.set()
            await asyncio.sleep(0.3)
            await history.add(make_check(user, "RU", NOW))

    async def second() -> None:
        await first_locked.wait()
        async with session_factory.begin() as session:
            history = PostgresCheckHistory(session)
            await history.lock_user(user)
            seen_by_second.append(await history.count_since(user, NOW - timedelta(minutes=10)))

    await asyncio.gather(first(), second())

    assert seen_by_second == [1]
