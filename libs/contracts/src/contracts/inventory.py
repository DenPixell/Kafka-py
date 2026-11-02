"""Команды и события сервиса inventory."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from contracts.envelope import Message


class OrderLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sku: str
    quantity: int = Field(gt=0)


class ReserveStock(Message):
    """Команда от order: отложить товары заказа на складе."""

    type: Literal["ReserveStock"] = "ReserveStock"
    lines: tuple[OrderLine, ...] = Field(min_length=1)
