from typing import Protocol
from uuid import UUID

from contracts import (
    InventoryCommand,
    Message,
    PricedLine,
    ReleaseStock,
    ReserveStock,
    StockReleased,
    StockReservationFailed,
    StockReserved,
)
from contracts.topics import INVENTORY_EVENTS
from inventory.domain.reservation import RequestedLine, ReservationResult, Reserved


class StockRepository(Protocol):
    async def reserve(self, order_id: UUID, lines: list[RequestedLine]) -> ReservationResult: ...

    async def release(self, order_id: UUID) -> None: ...


class Outbox(Protocol):
    async def put(self, topic: str, message: Message) -> None: ...


class ReservationService:
    """Обрабатывает команды саги и отвечает событием в inventory.events."""

    def __init__(self, stock: StockRepository, outbox: Outbox) -> None:
        self._stock = stock
        self._outbox = outbox

    async def handle(self, command: InventoryCommand) -> None:
        match command:
            case ReserveStock():
                await self._reserve(command)
            case ReleaseStock():
                await self._release(command)

    async def _reserve(self, command: ReserveStock) -> None:
        result = await self._stock.reserve(
            command.order_id,
            [RequestedLine(sku=line.sku, quantity=line.quantity) for line in command.lines],
        )
        reply: Message
        if isinstance(result, Reserved):
            reply = StockReserved(
                order_id=command.order_id,
                lines=tuple(
                    PricedLine(
                        sku=line.sku,
                        quantity=line.quantity,
                        unit_price_kopecks=line.unit_price_kopecks,
                    )
                    for line in result.lines
                ),
                total_kopecks=result.total_kopecks,
            )
        else:
            reply = StockReservationFailed(order_id=command.order_id, unavailable_skus=result.skus)
        await self._outbox.put(INVENTORY_EVENTS, reply)

    async def _release(self, command: ReleaseStock) -> None:
        await self._stock.release(command.order_id)
        # Отвечаем даже если снимать было нечего: саге важно знать, что резерва нет.
        await self._outbox.put(INVENTORY_EVENTS, StockReleased(order_id=command.order_id))
