"""Подделки хранилища и outbox в памяти: тесты сервиса и API работают без базы."""

from uuid import UUID

from contracts import Message
from order.domain.order import Order


class FakeOrderRepository:
    def __init__(self) -> None:
        self.orders: dict[UUID, Order] = {}

    async def add(self, order: Order) -> None:
        self.orders[order.id] = order

    async def get(self, order_id: UUID) -> Order | None:
        return self.orders.get(order_id)


class FakeOutbox:
    def __init__(self) -> None:
        self.messages: list[tuple[str, Message]] = []

    async def put(self, topic: str, message: Message) -> None:
        self.messages.append((topic, message))
