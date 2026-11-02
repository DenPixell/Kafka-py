from uuid import UUID, uuid4

from contracts import (
    Message,
    OrderLine,
    ReleaseStock,
    ReserveStock,
    StockReleased,
    StockReservationFailed,
    StockReserved,
)
from contracts.topics import INVENTORY_EVENTS
from inventory.domain.reservation import (
    RequestedLine,
    ReservationResult,
    Reserved,
    ReservedLine,
    Unavailable,
)
from inventory.service.reservations import ReservationService


class FakeStock:
    def __init__(self, result: ReservationResult) -> None:
        self.result = result
        self.released: list[UUID] = []

    async def reserve(self, order_id: UUID, lines: list[RequestedLine]) -> ReservationResult:
        return self.result

    async def release(self, order_id: UUID) -> None:
        self.released.append(order_id)


class FakeOutbox:
    def __init__(self) -> None:
        self.messages: list[tuple[str, Message]] = []

    async def put(self, topic: str, message: Message) -> None:
        self.messages.append((topic, message))


def reserve_command() -> ReserveStock:
    return ReserveStock(order_id=uuid4(), lines=(OrderLine(sku="macbook-neo-512", quantity=2),))


async def test_successful_reservation_replies_with_prices_and_total() -> None:
    outbox = FakeOutbox()
    stock = FakeStock(Reserved((ReservedLine("macbook-neo-512", 2, 7_999_000),)))
    command = reserve_command()

    await ReservationService(stock, outbox).handle(command)

    [(topic, reply)] = outbox.messages
    assert topic == INVENTORY_EVENTS
    assert isinstance(reply, StockReserved)
    assert reply.order_id == command.order_id
    assert reply.total_kopecks == 15_998_000


async def test_shortage_replies_with_unavailable_skus() -> None:
    outbox = FakeOutbox()

    await ReservationService(FakeStock(Unavailable(("macbook-neo-512",))), outbox).handle(
        reserve_command()
    )

    [(_, reply)] = outbox.messages
    assert isinstance(reply, StockReservationFailed)
    assert reply.unavailable_skus == ("macbook-neo-512",)


async def test_release_always_confirms() -> None:
    outbox = FakeOutbox()
    stock = FakeStock(Unavailable(("x",)))
    command = ReleaseStock(order_id=uuid4())

    await ReservationService(stock, outbox).handle(command)

    assert stock.released == [command.order_id]
    [(_, reply)] = outbox.messages
    assert isinstance(reply, StockReleased)
