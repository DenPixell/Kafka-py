from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from order.domain.order import CancelReason, Order, OrderItem, OrderStatus

# Код страны ISO 3166-1 alpha-2: RU, KZ, AM.
CountryCode = Annotated[str, StringConstraints(pattern=r"^[A-Z]{2}$")]


class OrderItemIn(BaseModel):
    sku: str = Field(min_length=1)
    quantity: int = Field(gt=0, le=10)

    def to_domain(self) -> OrderItem:
        return OrderItem(sku=self.sku, quantity=self.quantity)


class CreateOrderIn(BaseModel):
    # user_id здесь нет специально: он приходит только из заголовка X-User-Id.
    # extra="forbid": попытка передать его в теле — ошибка, а не тихое игнорирование.
    model_config = ConfigDict(extra="forbid")

    items: list[OrderItemIn] = Field(min_length=1, max_length=20)
    delivery_country: CountryCode

    @field_validator("items")
    @classmethod
    def skus_are_unique(cls, items: list[OrderItemIn]) -> list[OrderItemIn]:
        skus = [item.sku for item in items]
        if len(skus) != len(set(skus)):
            raise ValueError("Каждый артикул указывается один раз, количество — в quantity")
        return items


class OrderItemOut(BaseModel):
    sku: str
    quantity: int


class OrderOut(BaseModel):
    id: UUID
    status: OrderStatus
    delivery_country: str
    items: list[OrderItemOut]
    total_kopecks: int | None
    cancel_reason: CancelReason | None
    created_at: datetime

    @classmethod
    def from_domain(cls, order: Order) -> "OrderOut":
        return cls(
            id=order.id,
            status=order.status,
            delivery_country=order.delivery_country,
            items=[OrderItemOut(sku=i.sku, quantity=i.quantity) for i in order.items],
            total_kopecks=order.total_kopecks,
            cancel_reason=order.cancel_reason,
            created_at=order.created_at,
        )
