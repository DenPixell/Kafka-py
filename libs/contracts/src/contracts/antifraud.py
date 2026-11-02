"""Команды и события сервиса antifraud."""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from contracts.envelope import Message

# Команды: order → antifraud (топик antifraud.commands)


class CheckOrder(Message):
    """Проверить заказ. Сумма уже посчитана inventory по каталогу."""

    type: Literal["CheckOrder"] = "CheckOrder"
    user_id: str
    total_kopecks: int = Field(gt=0)
    delivery_country: str = Field(pattern=r"^[A-Z]{2}$")


# События: antifraud → order (топик antifraud.events)


class FraudCheckPassed(Message):
    type: Literal["FraudCheckPassed"] = "FraudCheckPassed"
    score: int = Field(ge=0)


class FraudCheckFailed(Message):
    """Заказ отклонён. reasons — сработавшие правила, чтобы решение можно было объяснить."""

    type: Literal["FraudCheckFailed"] = "FraudCheckFailed"
    score: int = Field(ge=0)
    reasons: tuple[str, ...] = Field(min_length=1)


AntifraudEvent = Annotated[FraudCheckPassed | FraudCheckFailed, Field(discriminator="type")]

antifraud_commands: TypeAdapter[CheckOrder] = TypeAdapter(CheckOrder)
antifraud_events: TypeAdapter[AntifraudEvent] = TypeAdapter(AntifraudEvent)
