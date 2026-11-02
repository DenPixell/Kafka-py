from uuid import uuid4

import pytest

from contracts import OrderLine, ReserveStock
from contracts.topics import INVENTORY_COMMANDS
from order.domain.errors import OrderNotFoundError
from order.domain.order import OrderItem, OrderStatus
from order.service.orders import OrderService

from .fakes import FakeOrderRepository, FakeOutbox

ITEMS = [OrderItem("iphone-17-256", 1), OrderItem("macbook-neo-512", 2)]


async def test_new_order_is_saved_in_reserving_status(
    service: OrderService, repository: FakeOrderRepository
) -> None:
    order = await service.place_order("anna", "RU", ITEMS)

    assert order.status is OrderStatus.RESERVING
    assert repository.orders[order.id] is order


async def test_new_order_asks_inventory_to_reserve(
    service: OrderService, outbox: FakeOutbox
) -> None:
    order = await service.place_order("anna", "RU", ITEMS)

    [(topic, message)] = outbox.messages
    assert topic == INVENTORY_COMMANDS
    assert isinstance(message, ReserveStock)
    assert message.order_id == order.id
    assert message.lines == (
        OrderLine(sku="iphone-17-256", quantity=1),
        OrderLine(sku="macbook-neo-512", quantity=2),
    )


async def test_owner_can_read_order(service: OrderService) -> None:
    order = await service.place_order("anna", "RU", ITEMS)

    assert await service.get_order(order.id, "anna") is order


async def test_other_user_gets_not_found(service: OrderService) -> None:
    order = await service.place_order("anna", "RU", ITEMS)

    with pytest.raises(OrderNotFoundError):
        await service.get_order(order.id, "boris")


async def test_missing_order_is_not_found(service: OrderService) -> None:
    with pytest.raises(OrderNotFoundError):
        await service.get_order(uuid4(), "anna")
