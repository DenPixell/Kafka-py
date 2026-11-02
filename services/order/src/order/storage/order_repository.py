from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from order.domain.order import CancelReason, Order, OrderItem, OrderStatus
from order.storage.tables import order_items, orders


class PostgresOrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, order: Order) -> None:
        await self._session.execute(
            insert(orders).values(
                id=order.id,
                user_id=order.user_id,
                status=order.status.value,
                delivery_country=order.delivery_country,
                total_kopecks=order.total_kopecks,
                cancel_reason=order.cancel_reason.value if order.cancel_reason else None,
                created_at=order.created_at,
            )
        )
        await self._session.execute(
            insert(order_items).values(
                [{"order_id": order.id, "sku": i.sku, "quantity": i.quantity} for i in order.items]
            )
        )

    async def get(self, order_id: UUID) -> Order | None:
        row = (await self._session.execute(select(orders).where(orders.c.id == order_id))).first()
        if row is None:
            return None
        items = await self._session.execute(
            select(order_items.c.sku, order_items.c.quantity)
            .where(order_items.c.order_id == order_id)
            .order_by(order_items.c.sku)
        )
        return Order(
            id=row.id,
            user_id=row.user_id,
            delivery_country=row.delivery_country,
            items=tuple(OrderItem(sku=i.sku, quantity=i.quantity) for i in items),
            status=OrderStatus(row.status),
            total_kopecks=row.total_kopecks,
            cancel_reason=CancelReason(row.cancel_reason) if row.cancel_reason else None,
            created_at=row.created_at,
        )
