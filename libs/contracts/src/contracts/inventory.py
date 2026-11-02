"""Команды и события сервиса inventory."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from contracts.envelope import Message


class OrderLine(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    sku: str
    quantity: int = Field(gt=0)


class PricedLine(OrderLine):
    unit_price_kopecks: int = Field(gt=0)


# Команды: order → inventory (топик inventory.commands)


class ReserveStock(Message):
    """Отложить товары заказа на складе."""

    type: Literal["ReserveStock"] = "ReserveStock"
    lines: tuple[OrderLine, ...] = Field(min_length=1)


class ReleaseStock(Message):
    """Компенсация: вернуть на склад всё, что отложено под заказ."""

    type: Literal["ReleaseStock"] = "ReleaseStock"


# События: inventory → order (топик inventory.events)


class StockReserved(Message):
    """Товары отложены. Цены взяты из каталога inventory, а не от клиента."""

    type: Literal["StockReserved"] = "StockReserved"
    lines: tuple[PricedLine, ...] = Field(min_length=1)
    total_kopecks: int = Field(gt=0)


class StockReservationFailed(Message):
    """Не хватило товара. Ничего не отложено."""

    type: Literal["StockReservationFailed"] = "StockReservationFailed"
    unavailable_skus: tuple[str, ...] = Field(min_length=1)


class StockReleased(Message):
    type: Literal["StockReleased"] = "StockReleased"


InventoryCommand = Annotated[ReserveStock | ReleaseStock, Field(discriminator="type")]
InventoryEvent = Annotated[
    StockReserved | StockReservationFailed | StockReleased, Field(discriminator="type")
]

# Разбор сообщения из Kafka в нужный класс по полю type.
inventory_commands: TypeAdapter[InventoryCommand] = TypeAdapter(InventoryCommand)
inventory_events: TypeAdapter[InventoryEvent] = TypeAdapter(InventoryEvent)
