"""Заказ и сообщение в outbox на настоящем PostgreSQL: сохраняются или откатываются вместе."""

from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Table, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from testcontainers.community.postgres import PostgresContainer

from contracts import ReserveStock
from messaging import OutboxWriter
from order.domain.order import CancelReason, OrderItem, OrderStatus
from order.service.orders import OrderService
from order.storage.db import create_engine, create_session_factory
from order.storage.order_repository import PostgresOrderRepository
from order.storage.tables import orders, outbox

pytestmark = pytest.mark.integration

ALEMBIC_INI = Path(__file__).parents[2] / "alembic.ini"
ITEMS = [OrderItem("iphone-17-256", 1), OrderItem("macbook-neo-512", 2)]


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
    factory = create_session_factory(engine)
    yield factory
    await engine.dispose()


def make_service(session: AsyncSession) -> OrderService:
    return OrderService(PostgresOrderRepository(session), OutboxWriter(session, outbox))


async def count(factory: async_sessionmaker[AsyncSession], table: Table) -> int:
    async with factory() as session:
        return int(await session.scalar(select(func.count()).select_from(table)) or 0)


async def test_order_round_trip(session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory.begin() as session:
        placed = await make_service(session).place_order("anna", "RU", ITEMS)

    async with session_factory() as session:
        loaded = await make_service(session).get_order(placed.id, "anna")

    assert loaded.status is OrderStatus.RESERVING
    assert loaded.items == tuple(ITEMS)
    assert loaded.created_at == placed.created_at


async def test_order_and_command_are_committed_together(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        placed = await make_service(session).place_order("anna", "RU", ITEMS)

    async with session_factory() as session:
        payload = await session.scalar(
            select(outbox.c.payload).where(outbox.c.key == str(placed.id))
        )

    command = ReserveStock.model_validate(payload)
    assert [line.sku for line in command.lines] == ["iphone-17-256", "macbook-neo-512"]


async def test_rollback_drops_both_order_and_command(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    orders_before = await count(session_factory, orders)
    outbox_before = await count(session_factory, outbox)

    async with session_factory() as session:
        await make_service(session).place_order("anna", "RU", ITEMS)
        await session.rollback()

    assert await count(session_factory, orders) == orders_before
    assert await count(session_factory, outbox) == outbox_before


async def test_update_persists_saga_progress(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory.begin() as session:
        placed = await make_service(session).place_order("anna", "RU", ITEMS)

    async with session_factory.begin() as session:
        repository = PostgresOrderRepository(session)
        order = await repository.get(placed.id, for_update=True)
        assert order is not None
        order.mark_reserved(total_kopecks=15_998_000)
        order.reject_by_fraud()
        await repository.update(order)

    async with session_factory() as session:
        loaded = await PostgresOrderRepository(session).get(placed.id)

    assert loaded is not None
    assert loaded.status is OrderStatus.CANCELLING
    assert loaded.total_kopecks == 15_998_000
    assert loaded.cancel_reason is CancelReason.FRAUD
