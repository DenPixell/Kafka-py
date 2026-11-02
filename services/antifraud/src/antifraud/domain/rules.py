"""Антифрод-правила и подсчёт баллов.

Каждое сработавшее правило добавляет баллы. Если сумма не меньше порога,
заказ отклоняется. Правило не решает всё само: крупная сумма от постоянного
покупателя — нормально, а крупная сумма в новую страну — уже подозрительно.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CheckContext:
    """Всё, что известно о заказе и истории покупателя на момент проверки."""

    total_kopecks: int
    delivery_country: str
    # Сколько заказов покупатель сделал за окно правила частых заказов, не считая этот.
    recent_orders: int
    # Страны одобренных раньше заказов. Пусто — покупатель новый.
    known_countries: frozenset[str]


class Rule(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def score(self) -> int: ...

    def applies(self, context: CheckContext) -> bool: ...


@dataclass(frozen=True)
class LargeAmount:
    threshold_kopecks: int
    score: int
    name: str = "large_amount"

    def applies(self, context: CheckContext) -> bool:
        return context.total_kopecks > self.threshold_kopecks


@dataclass(frozen=True)
class FrequentOrders:
    max_orders: int
    score: int
    name: str = "frequent_orders"

    def applies(self, context: CheckContext) -> bool:
        # Этот заказ тоже считается: max_orders=3 значит «четвёртый за окно — подозрительно».
        return context.recent_orders + 1 > self.max_orders


@dataclass(frozen=True)
class NewCountry:
    threshold_kopecks: int
    score: int
    name: str = "new_country"

    def applies(self, context: CheckContext) -> bool:
        # У нового покупателя «смены страны» нет: сравнивать не с чем.
        return (
            bool(context.known_countries)
            and context.delivery_country not in context.known_countries
            and context.total_kopecks > self.threshold_kopecks
        )


@dataclass(frozen=True)
class Verdict:
    score: int
    reasons: tuple[str, ...]
    approved: bool


def evaluate(context: CheckContext, rules: list[Rule], reject_threshold: int) -> Verdict:
    triggered = [rule for rule in rules if rule.applies(context)]
    score = sum(rule.score for rule in triggered)
    return Verdict(
        score=score,
        reasons=tuple(rule.name for rule in triggered),
        approved=score < reject_threshold,
    )
