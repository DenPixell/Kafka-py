from typing import Protocol
from uuid import UUID

from contracts import Message, OrderLine, ReserveStock
from contracts.topics import INVENTORY_COMMANDS
from order.domain.errors import OrderNotFoundError
from order.domain.order import Order, OrderItem


class OrderRepository(Protocol):
    async def add(self, order: Order) -> None: ...

    async def get(self, order_id: UUID, *, for_update: bool = False) -> Order | None: ...

    async def update(self, order: Order) -> None: ...


class Outbox(Protocol):
    async def put(self, topic: str, message: Message) -> None: ...


class OrderService:
    """Репозиторий и outbox работают в одной транзакции: её открывает и
    коммитит вызывающий код (HTTP-обработчик)."""

    def __init__(self, orders: OrderRepository, outbox: Outbox) -> None:
        self._orders = orders
        self._outbox = outbox

    async def place_order(
        self, user_id: str, delivery_country: str, items: list[OrderItem]
    ) -> Order:
        order = Order(user_id=user_id, delivery_country=delivery_country, items=tuple(items))
        order.start_reservation()
        await self._orders.add(order)
        # Первый шаг саги: попросить inventory отложить товары.
        await self._outbox.put(
            INVENTORY_COMMANDS,
            ReserveStock(
                order_id=order.id,
                lines=tuple(OrderLine(sku=i.sku, quantity=i.quantity) for i in order.items),
            ),
        )
        return order

    async def get_order(self, order_id: UUID, user_id: str) -> Order:
        order = await self._orders.get(order_id)
        # Чужой заказ неотличим от несуществующего: так нельзя перебором узнать чужие id.
        if order is None or order.user_id != user_id:
            raise OrderNotFoundError(order_id)
        return order
