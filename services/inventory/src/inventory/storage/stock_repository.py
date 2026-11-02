from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.domain.reservation import (
    RequestedLine,
    ReservationResult,
    Reserved,
    ReservedLine,
    Unavailable,
)
from inventory.storage.tables import product_variants, reservations, stock


class _NotEnoughStockError(Exception):
    def __init__(self, skus: list[str]) -> None:
        self.skus = skus


class PostgresStockRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def reserve(self, order_id: UUID, lines: list[RequestedLine]) -> ReservationResult:
        existing = await self._reserved_lines(order_id)
        if existing:
            # Повторная команда для того же заказа: отвечаем тем же резервом.
            return Reserved(existing)

        prices = await self._prices([line.sku for line in lines])
        try:
            # SAVEPOINT: если хоть одной позиции не хватит, откатятся все уже
            # отложенные строки этого заказа, а внешняя транзакция продолжится.
            async with self._session.begin_nested():
                await self._reserve_all(lines, prices)
        except _NotEnoughStockError as error:
            return Unavailable(tuple(error.skus))

        reserved = tuple(
            ReservedLine(sku=line.sku, quantity=line.quantity, unit_price_kopecks=prices[line.sku])
            for line in sorted(lines, key=lambda line: line.sku)
        )
        await self._session.execute(
            insert(reservations).values(
                [
                    {
                        "order_id": order_id,
                        "sku": line.sku,
                        "quantity": line.quantity,
                        "unit_price_kopecks": line.unit_price_kopecks,
                    }
                    for line in reserved
                ]
            )
        )
        return Reserved(reserved)

    async def release(self, order_id: UUID) -> None:
        rows = (
            await self._session.execute(
                select(reservations.c.sku, reservations.c.quantity)
                .where(reservations.c.order_id == order_id, reservations.c.released_at.is_(None))
                .order_by(reservations.c.sku)
                .with_for_update()
            )
        ).all()
        for row in rows:
            await self._session.execute(
                update(stock)
                .where(stock.c.sku == row.sku)
                .values(reserved=stock.c.reserved - row.quantity)
            )
        await self._session.execute(
            update(reservations)
            .where(reservations.c.order_id == order_id, reservations.c.released_at.is_(None))
            .values(released_at=func.now())
        )

    async def _reserve_all(self, lines: list[RequestedLine], prices: dict[str, int]) -> None:
        missing = []
        # Один порядок блокировок для всех заказов: так два заказа не застрянут
        # в deadlock, ожидая строки друг друга.
        for line in sorted(lines, key=lambda line: line.sku):
            if line.sku not in prices or not await self._take(line):
                missing.append(line.sku)
        if missing:
            raise _NotEnoughStockError(missing)

    async def _take(self, line: RequestedLine) -> bool:
        """Атомарно откладывает товар, если его хватает. Проверка и запись — один запрос,
        поэтому два параллельных заказа не смогут отложить последний товар дважды."""
        result = await self._session.execute(
            update(stock)
            .where(stock.c.sku == line.sku, stock.c.quantity - stock.c.reserved >= line.quantity)
            .values(reserved=stock.c.reserved + line.quantity)
            .returning(stock.c.sku)
        )
        return result.first() is not None

    async def _prices(self, skus: list[str]) -> dict[str, int]:
        result = await self._session.execute(
            select(product_variants.c.sku, product_variants.c.price_kopecks).where(
                product_variants.c.sku.in_(skus)
            )
        )
        return {row.sku: row.price_kopecks for row in result}

    async def _reserved_lines(self, order_id: UUID) -> tuple[ReservedLine, ...]:
        result = await self._session.execute(
            select(reservations.c.sku, reservations.c.quantity, reservations.c.unit_price_kopecks)
            .where(reservations.c.order_id == order_id)
            .order_by(reservations.c.sku)
        )
        return tuple(
            ReservedLine(sku=r.sku, quantity=r.quantity, unit_price_kopecks=r.unit_price_kopecks)
            for r in result
        )
