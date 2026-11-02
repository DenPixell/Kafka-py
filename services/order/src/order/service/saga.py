"""Оркестратор саги: по ответам других сервисов двигает заказ дальше."""

import logging

from contracts import (
    CheckOrder,
    InventoryEvent,
    StockReleased,
    StockReservationFailed,
    StockReserved,
)
from contracts.topics import ANTIFRAUD_COMMANDS
from order.domain.errors import InvalidTransitionError
from order.domain.order import Order
from order.service.orders import OrderRepository, Outbox

logger = logging.getLogger(__name__)


class SagaService:
    def __init__(self, orders: OrderRepository, outbox: Outbox) -> None:
        self._orders = orders
        self._outbox = outbox

    async def on_inventory_event(self, event: InventoryEvent) -> None:
        order = await self._orders.get(event.order_id, for_update=True)
        if order is None:
            logger.warning("Событие %s для неизвестного заказа %s", event.type, event.order_id)
            return
        try:
            await self._apply(order, event)
        except InvalidTransitionError:
            # Событие не к месту: например, опоздавший дубль. Заказ не меняем.
            logger.warning(
                "Заказ %s в статусе %s: событие %s пропущено", order.id, order.status, event.type
            )
            return
        await self._orders.update(order)

    async def _apply(self, order: Order, event: InventoryEvent) -> None:
        match event:
            case StockReserved():
                order.mark_reserved(event.total_kopecks)
                # Следующий шаг саги: проверка антифродом.
                await self._outbox.put(
                    ANTIFRAUD_COMMANDS,
                    CheckOrder(
                        order_id=order.id,
                        user_id=order.user_id,
                        total_kopecks=event.total_kopecks,
                        delivery_country=order.delivery_country,
                    ),
                )
            case StockReservationFailed():
                order.reject_out_of_stock()
            case StockReleased():
                order.mark_released()
