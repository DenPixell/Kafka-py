"""Общий конверт для всех сообщений в Kafka.

Каждая команда и каждое событие наследуются от Message, поэтому у любого
сообщения есть поля, на которые опирается надёжная доставка:
message_id для идемпотентности и order_id как ключ партиции.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Message(BaseModel):
    """Базовое сообщение. Конкретные команды и события задают своё значение type."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    message_id: UUID = Field(default_factory=uuid4)
    type: str
    version: int = 1
    # AwareDatetime не пропустит время без часового пояса: в системе всё хранится в UTC.
    occurred_at: AwareDatetime = Field(default_factory=_utc_now)
    order_id: UUID

    def partition_key(self) -> bytes:
        """Ключ сообщения в Kafka: все сообщения одного заказа идут в одну партицию."""
        return str(self.order_id).encode()
