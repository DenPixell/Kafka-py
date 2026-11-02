from uuid import uuid4

import pytest

from contracts import (
    CheckOrder,
    FraudCheckFailed,
    FraudCheckPassed,
    PricedLine,
    ReleaseStock,
    StockReleased,
    StockReservationFailed,
    StockReserved,
)
from contracts.topics import ANTIFRAUD_COMMANDS, INVENTORY_COMMANDS
from order.domain.order import CancelReason, Order, OrderItem, OrderStatus
from order.service.saga import SagaService

from .fakes import FakeOrderRepository, FakeOutbox


@pytest.fixture
def order(repository: FakeOrderRepository) -> Order:
    order = Order(user_id="anna", delivery_country="KZ", items=(OrderItem("macbook-neo-512", 2),))
    order.start_reservation()
    repository.orders[order.id] = order
    return order


@pytest.fixture
def saga(repository: FakeOrderRepository, outbox: FakeOutbox) -> SagaService:
    return SagaService(repository, outbox)


def stock_reserved(order: Order) -> StockReserved:
    return StockReserved(
        order_id=order.id,
        lines=(PricedLine(sku="macbook-neo-512", quantity=2, unit_price_kopecks=7_999_000),),
        total_kopecks=15_998_000,
    )


async def test_reserved_order_goes_to_fraud_check(
    saga: SagaService, order: Order, repository: FakeOrderRepository, outbox: FakeOutbox
) -> None:
    await saga.on_event(stock_reserved(order))

    assert order.status is OrderStatus.FRAUD_CHECK
    assert order.total_kopecks == 15_998_000
    assert repository.updated == [OrderStatus.FRAUD_CHECK]
    [(topic, command)] = outbox.messages
    assert topic == ANTIFRAUD_COMMANDS
    assert outbox.keys == ["anna"]
    assert command == CheckOrder(
        message_id=command.message_id,
        occurred_at=command.occurred_at,
        order_id=order.id,
        user_id="anna",
        total_kopecks=15_998_000,
        delivery_country="KZ",
    )


async def test_shortage_cancels_order(saga: SagaService, order: Order) -> None:
    await saga.on_event(
        StockReservationFailed(order_id=order.id, unavailable_skus=("macbook-neo-512",))
    )

    assert order.status is OrderStatus.CANCELLED
    assert order.cancel_reason is CancelReason.OUT_OF_STOCK


async def test_release_finishes_cancellation(saga: SagaService, order: Order) -> None:
    order.mark_reserved(15_998_000)
    order.reject_by_fraud()

    await saga.on_event(StockReleased(order_id=order.id))

    assert order.status is OrderStatus.CANCELLED


async def test_out_of_place_event_is_skipped(
    saga: SagaService, order: Order, repository: FakeOrderRepository, outbox: FakeOutbox
) -> None:
    await saga.on_event(stock_reserved(order))

    # Тот же результат резерва пришёл второй раз с другим message_id.
    await saga.on_event(stock_reserved(order))

    assert order.status is OrderStatus.FRAUD_CHECK
    assert repository.updated == [OrderStatus.FRAUD_CHECK]
    assert len(outbox.messages) == 1


async def test_event_for_unknown_order_is_ignored(
    saga: SagaService, repository: FakeOrderRepository
) -> None:
    await saga.on_event(StockReleased(order_id=uuid4()))

    assert repository.updated == []


async def test_passed_check_confirms_order(saga: SagaService, order: Order) -> None:
    order.mark_reserved(15_998_000)

    await saga.on_event(FraudCheckPassed(order_id=order.id, score=0))

    assert order.status is OrderStatus.CONFIRMED


async def test_failed_check_starts_compensation(
    saga: SagaService, order: Order, outbox: FakeOutbox
) -> None:
    order.mark_reserved(15_998_000)

    await saga.on_event(FraudCheckFailed(order_id=order.id, score=90, reasons=("new_country",)))

    assert order.status is OrderStatus.CANCELLING
    assert order.cancel_reason is CancelReason.FRAUD
    [(topic, command)] = outbox.messages
    assert topic == INVENTORY_COMMANDS
    assert command == ReleaseStock(
        message_id=command.message_id, occurred_at=command.occurred_at, order_id=order.id
    )
