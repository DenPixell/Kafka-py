import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer

from inventory.seed.catalog import load_catalog, seed_catalog
from inventory.storage.db import create_engine, create_session_factory

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"


async def _seed(url: str) -> None:
    engine = create_engine(url)
    async with create_session_factory(engine).begin() as session:
        await seed_catalog(session, load_catalog())
    await engine.dispose()


@pytest.fixture(scope="package")
def database_url() -> Iterator[str]:
    """Одна база на все интеграционные тесты: миграции и каталог применяются один раз."""
    with PostgresContainer("postgres:17.11-alpine", driver="asyncpg") as postgres:
        url = postgres.get_connection_url()
        config = Config(ALEMBIC_INI)
        config.set_main_option("sqlalchemy.url", url)
        command.upgrade(config, "head")
        asyncio.run(_seed(url))
        yield url


@pytest.fixture
async def session_factory(database_url: str) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(database_url)
    yield create_session_factory(engine)
    await engine.dispose()


@pytest.fixture
async def session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Сессия, изменения которой откатываются после теста."""
    async with session_factory() as session:
        yield session
        await session.rollback()
