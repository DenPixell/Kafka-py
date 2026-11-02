"""Команды и события сервиса antifraud."""

from typing import Literal

from pydantic import Field

from contracts.envelope import Message

# Команды: order → antifraud (топик antifraud.commands)


class CheckOrder(Message):
    """Проверить заказ. Сумма уже посчитана inventory по каталогу."""

    type: Literal["CheckOrder"] = "CheckOrder"
    user_id: str
    total_kopecks: int = Field(gt=0)
    delivery_country: str = Field(pattern=r"^[A-Z]{2}$")
