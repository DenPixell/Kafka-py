from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from antifraud.domain.rules import Verdict


@dataclass(frozen=True)
class FraudCheck:
    """Проверенный заказ. По этим записям считается история покупателя."""

    order_id: UUID
    user_id: str
    total_kopecks: int
    delivery_country: str
    checked_at: datetime
    verdict: Verdict
