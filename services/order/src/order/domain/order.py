"""Заказ и его машина состояний.

NEW → RESERVING → FRAUD_CHECK → CONFIRMED
          │             │
          │             └→ CANCELLING → CANCELLED   (антифрод отклонил, снимаем резерв)
          └→ CANCELLED                              (товара нет, откатывать нечего)
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from order.domain.errors import InvalidTransitionError


class OrderStatus(StrEnum):
    NEW = "NEW"
    RESERVING = "RESERVING"
    FRAUD_CHECK = "FRAUD_CHECK"
    CONFIRMED = "CONFIRMED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"


class CancelReason(StrEnum):
    OUT_OF_STOCK = "out_of_stock"
    FRAUD = "fraud"


ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.NEW: frozenset({OrderStatus.RESERVING}),
    OrderStatus.RESERVING: frozenset({OrderStatus.FRAUD_CHECK, OrderStatus.CANCELLED}),
    OrderStatus.FRAUD_CHECK: frozenset({OrderStatus.CONFIRMED, OrderStatus.CANCELLING}),
    OrderStatus.CANCELLING: frozenset({OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True)
class OrderItem:
    sku: str
    quantity: int


@dataclass
class Order:
    user_id: str
    delivery_country: str
    items: tuple[OrderItem, ...]
    id: UUID = field(default_factory=uuid4)
    status: OrderStatus = OrderStatus.NEW
    # Сумму считает inventory по своему каталогу, до резерва она неизвестна.
    total_kopecks: int | None = None
    cancel_reason: CancelReason | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def start_reservation(self) -> None:
        self._move_to(OrderStatus.RESERVING)

    def mark_reserved(self, total_kopecks: int) -> None:
        self._move_to(OrderStatus.FRAUD_CHECK)
        self.total_kopecks = total_kopecks

    def reject_out_of_stock(self) -> None:
        self._move_to(OrderStatus.CANCELLED)
        self.cancel_reason = CancelReason.OUT_OF_STOCK

    def confirm(self) -> None:
        self._move_to(OrderStatus.CONFIRMED)

    def reject_by_fraud(self) -> None:
        self._move_to(OrderStatus.CANCELLING)
        self.cancel_reason = CancelReason.FRAUD

    def mark_released(self) -> None:
        self._move_to(OrderStatus.CANCELLED)

    def _move_to(self, new_status: OrderStatus) -> None:
        if new_status not in ALLOWED_TRANSITIONS[self.status]:
            raise InvalidTransitionError(
                f"Заказ {self.id}: переход {self.status} → {new_status} недопустим"
            )
        self.status = new_status
