from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from antifraud.config import Settings
from antifraud.domain.check import FraudCheck
from antifraud.service.checks import FraudCheckService
from contracts import CheckOrder, FraudCheckFailed, FraudCheckPassed, Message
from contracts.topics import ANTIFRAUD_EVENTS

SETTINGS = Settings(database_url="postgresql+asyncpg://user:pass@localhost/test")
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)


class FakeHistory:
    def __init__(self) -> None:
        self.checks: dict[UUID, FraudCheck] = {}
        self.locked: list[str] = []

    async def lock_user(self, user_id: str) -> None:
        self.locked.append(user_id)

    async def find(self, order_id: UUID) -> FraudCheck | None:
        return self.checks.get(order_id)

    async def count_since(self, user_id: str, since: datetime) -> int:
        return sum(
            1 for c in self.checks.values() if c.user_id == user_id and c.checked_at >= since
        )

    async def approved_countries(self, user_id: str) -> frozenset[str]:
        return frozenset(
            c.delivery_country
            for c in self.checks.values()
            if c.user_id == user_id and c.verdict.approved
        )

    async def add(self, check: FraudCheck) -> None:
        self.checks[check.order_id] = check


class FakeOutbox:
    def __init__(self) -> None:
        self.messages: list[tuple[str, Message]] = []

    async def put(self, topic: str, message: Message) -> None:
        self.messages.append((topic, message))


def make_service(history: FakeHistory, outbox: FakeOutbox) -> FraudCheckService:
    return FraudCheckService(
        history,
        outbox,
        SETTINGS.rules(),
        SETTINGS.reject_threshold,
        SETTINGS.frequent_orders_window,
    )


def check_order(
    total_rub: int = 80_000, country: str = "RU", at: datetime = NOW, user: str = "anna"
) -> CheckOrder:
    return CheckOrder(
        order_id=uuid4(),
        user_id=user,
        total_kopecks=total_rub * 100,
        delivery_country=country,
        occurred_at=at,
    )


async def test_ordinary_order_passes() -> None:
    history, outbox = FakeHistory(), FakeOutbox()

    await make_service(history, outbox).handle(check_order())

    [(topic, reply)] = outbox.messages
    assert topic == ANTIFRAUD_EVENTS
    assert isinstance(reply, FraudCheckPassed)
    assert history.locked == ["anna"]


async def test_fourth_order_in_ten_minutes_is_rejected() -> None:
    history, outbox = FakeHistory(), FakeOutbox()
    service = make_service(history, outbox)

    for minute in range(4):
        await service.handle(check_order(at=NOW + timedelta(minutes=minute)))

    replies = [reply for _, reply in outbox.messages]
    assert [type(r).__name__ for r in replies] == ["FraudCheckPassed"] * 3 + ["FraudCheckFailed"]
    assert isinstance(replies[3], FraudCheckFailed)
    assert replies[3].reasons == ("frequent_orders",)


async def test_orders_outside_window_do_not_count() -> None:
    history, outbox = FakeHistory(), FakeOutbox()
    service = make_service(history, outbox)

    for minute in (0, 5, 15, 20):
        await service.handle(check_order(at=NOW + timedelta(minutes=minute)))

    assert all(isinstance(reply, FraudCheckPassed) for _, reply in outbox.messages)


async def test_expensive_order_to_new_country_is_rejected() -> None:
    history, outbox = FakeHistory(), FakeOutbox()
    service = make_service(history, outbox)
    await service.handle(check_order(country="RU", at=NOW - timedelta(days=30)))

    await service.handle(check_order(total_rub=589_990, country="AM"))

    _, reply = outbox.messages[-1]
    assert isinstance(reply, FraudCheckFailed)
    assert reply.reasons == ("large_amount", "new_country")


async def test_repeated_command_gets_same_answer_without_new_check() -> None:
    history, outbox = FakeHistory(), FakeOutbox()
    service = make_service(history, outbox)
    command = check_order()

    await service.handle(command)
    await service.handle(command.model_copy(update={"message_id": uuid4()}))

    assert len(history.checks) == 1
    assert outbox.messages[0][1].type == outbox.messages[1][1].type == "FraudCheckPassed"
