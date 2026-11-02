import pytest

from order.domain.errors import InvalidTransitionError
from order.domain.order import CancelReason, Order, OrderItem, OrderStatus


def make_order() -> Order:
    return Order(user_id="anna", delivery_country="RU", items=(OrderItem("iphone-17-256", 1),))


def test_happy_path() -> None:
    order = make_order()

    order.start_reservation()
    order.mark_reserved(total_kopecks=7_999_000)
    order.confirm()

    assert order.status is OrderStatus.CONFIRMED
    assert order.total_kopecks == 7_999_000
    assert order.cancel_reason is None


def test_out_of_stock_cancels_right_away() -> None:
    order = make_order()
    order.start_reservation()

    order.reject_out_of_stock()

    assert order.status is OrderStatus.CANCELLED
    assert order.cancel_reason is CancelReason.OUT_OF_STOCK


def reserved_order() -> Order:
    order = make_order()
    order.start_reservation()
    order.mark_reserved(total_kopecks=7_999_000)
    return order


def test_fraud_rejection_waits_for_stock_release() -> None:
    order = reserved_order()

    order.reject_by_fraud()

    assert order.status is OrderStatus.CANCELLING
    assert order.cancel_reason is CancelReason.FRAUD


def test_released_stock_completes_cancellation() -> None:
    order = reserved_order()
    order.reject_by_fraud()

    order.mark_released()

    assert order.status is OrderStatus.CANCELLED


def test_cannot_confirm_before_fraud_check() -> None:
    order = make_order()
    order.start_reservation()

    with pytest.raises(InvalidTransitionError):
        order.confirm()


def test_final_status_does_not_change() -> None:
    order = make_order()
    order.start_reservation()
    order.reject_out_of_stock()

    with pytest.raises(InvalidTransitionError):
        order.start_reservation()


def test_failed_transition_keeps_previous_status() -> None:
    order = make_order()

    with pytest.raises(InvalidTransitionError):
        order.mark_reserved(total_kopecks=1)

    assert order.status is OrderStatus.NEW
    assert order.total_kopecks is None
