from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from antifraud.domain.check import FraudCheck
from antifraud.domain.rules import CheckContext, Rule, evaluate
from contracts import CheckOrder, FraudCheckFailed, FraudCheckPassed, Message
from contracts.topics import ANTIFRAUD_EVENTS


class CheckHistory(Protocol):
    async def lock_user(self, user_id: str) -> None: ...

    async def find(self, order_id: UUID) -> FraudCheck | None: ...

    async def count_since(self, user_id: str, since: datetime) -> int: ...

    async def approved_countries(self, user_id: str) -> frozenset[str]: ...

    async def add(self, check: FraudCheck) -> None: ...


class Outbox(Protocol):
    async def put(self, topic: str, message: Message) -> None: ...


class FraudCheckService:
    def __init__(
        self,
        history: CheckHistory,
        outbox: Outbox,
        rules: list[Rule],
        reject_threshold: int,
        frequent_orders_window: timedelta,
    ) -> None:
        self._history = history
        self._outbox = outbox
        self._rules = rules
        self._reject_threshold = reject_threshold
        self._window = frequent_orders_window

    async def handle(self, command: CheckOrder) -> None:
        # Проверки одного покупателя идут по очереди. Иначе два параллельных заказа
        # не увидят друг друга в истории и правило частых заказов не сработает.
        await self._history.lock_user(command.user_id)
        check = await self._history.find(command.order_id)
        if check is None:
            check = await self._check(command)
            await self._history.add(check)
        # Повторная команда получает то же решение, правила второй раз не применяются.
        await self._outbox.put(ANTIFRAUD_EVENTS, _reply(check))

    async def _check(self, command: CheckOrder) -> FraudCheck:
        # Окно считается от времени события, а не от текущего: если воркер отстал,
        # решение не зависит от того, когда до сообщения дошла очередь.
        context = CheckContext(
            total_kopecks=command.total_kopecks,
            delivery_country=command.delivery_country,
            recent_orders=await self._history.count_since(
                command.user_id, command.occurred_at - self._window
            ),
            known_countries=await self._history.approved_countries(command.user_id),
        )
        return FraudCheck(
            order_id=command.order_id,
            user_id=command.user_id,
            total_kopecks=command.total_kopecks,
            delivery_country=command.delivery_country,
            checked_at=command.occurred_at,
            verdict=evaluate(context, self._rules, self._reject_threshold),
        )


def _reply(check: FraudCheck) -> Message:
    if check.verdict.approved:
        return FraudCheckPassed(order_id=check.order_id, score=check.verdict.score)
    return FraudCheckFailed(
        order_id=check.order_id, score=check.verdict.score, reasons=check.verdict.reasons
    )
