"""Резерв на настоящем PostgreSQL: атомарность, откат и параллельные заказы."""

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from inventory.domain.reservation import RequestedLine, ReservationResult, Reserved, Unavailable
from inventory.storage.stock_repository import PostgresStockRepository
from inventory.storage.tables import stock

pytestmark = pytest.mark.integration

NEO_256 = "macbook-neo-256"  # 10 штук, 69 990 ₽
NEO_512 = "macbook-neo-512"  # 10 штук, 79 990 ₽


async def reserved(session: AsyncSession, sku: str) -> int:
    return int(await session.scalar(select(stock.c.reserved).where(stock.c.sku == sku)) or 0)


async def test_reserves_all_lines_with_catalog_prices(session: AsyncSession) -> None:
    result = await PostgresStockRepository(session).reserve(
        uuid4(), [RequestedLine(NEO_512, 2), RequestedLine(NEO_256, 1)]
    )

    assert isinstance(result, Reserved)
    assert result.total_kopecks == 2 * 7_999_000 + 6_999_000
    assert await reserved(session, NEO_512) == 2
    assert await reserved(session, NEO_256) == 1


async def test_shortage_reserves_nothing(session: AsyncSession) -> None:
    result = await PostgresStockRepository(session).reserve(
        uuid4(), [RequestedLine(NEO_256, 1), RequestedLine(NEO_512, 11)]
    )

    assert result == Unavailable((NEO_512,))
    # Строка NEO_256 успела отложиться, но SAVEPOINT откатил и её.
    assert await reserved(session, NEO_256) == 0


async def test_unknown_sku_is_unavailable(session: AsyncSession) -> None:
    result = await PostgresStockRepository(session).reserve(
        uuid4(), [RequestedLine("iphone-99-256", 1)]
    )

    assert result == Unavailable(("iphone-99-256",))


async def test_repeated_command_does_not_reserve_twice(session: AsyncSession) -> None:
    repository = PostgresStockRepository(session)
    order_id = uuid4()

    first = await repository.reserve(order_id, [RequestedLine(NEO_256, 3)])
    second = await repository.reserve(order_id, [RequestedLine(NEO_256, 3)])

    assert first == second
    assert await reserved(session, NEO_256) == 3


async def test_release_returns_stock_once(session: AsyncSession) -> None:
    repository = PostgresStockRepository(session)
    order_id = uuid4()
    await repository.reserve(order_id, [RequestedLine(NEO_256, 3)])

    await repository.release(order_id)
    await repository.release(order_id)

    assert await reserved(session, NEO_256) == 0


async def test_parallel_orders_cannot_take_the_last_unit(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    last_unit = "macbook-pro-m5-max-16-8192"  # на складе одна штука

    async def place(order_id: UUID) -> ReservationResult:
        async with session_factory.begin() as session:
            return await PostgresStockRepository(session).reserve(
                order_id, [RequestedLine(last_unit, 1)]
            )

    results = await asyncio.gather(place(uuid4()), place(uuid4()))

    assert sorted(type(r).__name__ for r in results) == ["Reserved", "Unavailable"]
