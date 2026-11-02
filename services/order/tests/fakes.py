"""Подделки хранилища и outbox в памяти: тесты сервиса и API работают без базы."""

from uuid import UUID

from contracts import Message
from order.domain.order import Order, OrderStatus


class FakeOrderRepository:
    def __init__(self) -> None:
        self.orders: dict[UUID, Order] = {}
        # Статусы, с которыми заказ сохранялся: видно, что сага его записала.
        self.updated: list[OrderStatus] = []

    async def add(self, order: Order) -> None:
        self.orders[order.id] = order

    async def get(self, order_id: UUID, *, for_update: bool = False) -> Order | None:
        return self.orders.get(order_id)

    async def update(self, order: Order) -> None:
        self.updated.append(order.status)


class FakeOutbox:
    def __init__(self) -> None:
        self.messages: list[tuple[str, Message]] = []
        self.keys: list[str | None] = []

    async def put(self, topic: str, message: Message, key: str | None = None) -> None:
        self.messages.append((topic, message))
        self.keys.append(key)
