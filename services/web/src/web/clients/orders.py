"""HTTP-клиент сервиса order."""

from datetime import datetime
from uuid import UUID

import httpx
from pydantic import BaseModel, TypeAdapter

from web.clients.errors import ServiceUnavailableError

FINAL_STATUSES = frozenset({"CONFIRMED", "CANCELLED"})


class OrderItem(BaseModel):
    sku: str
    quantity: int


class Order(BaseModel):
    id: UUID
    status: str
    delivery_country: str
    items: list[OrderItem]
    total_kopecks: int | None
    cancel_reason: str | None
    created_at: datetime

    @property
    def is_final(self) -> bool:
        return self.status in FINAL_STATUSES


_orders = TypeAdapter(list[Order])


class OrderClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def create(self, user_id: str, items: dict[str, int], delivery_country: str) -> Order:
        response = await self._request(
            "POST",
            "/orders",
            user_id,
            json={
                "items": [{"sku": sku, "quantity": qty} for sku, qty in items.items()],
                "delivery_country": delivery_country,
            },
        )
        return Order.model_validate_json(response.content)

    async def get(self, user_id: str, order_id: UUID) -> Order | None:
        response = await self._request("GET", f"/orders/{order_id}", user_id, allow_not_found=True)
        return None if response.status_code == 404 else Order.model_validate_json(response.content)

    async def list(self, user_id: str) -> list[Order]:
        response = await self._request("GET", "/orders", user_id)
        return _orders.validate_json(response.content)

    async def _request(
        self,
        method: str,
        path: str,
        user_id: str,
        json: object = None,
        allow_not_found: bool = False,
    ) -> httpx.Response:
        try:
            # Витрина играет роль API Gateway: передаёт покупателя заголовком.
            response = await self._http.request(
                method, path, json=json, headers={"X-User-Id": user_id}
            )
        except httpx.HTTPError as error:
            raise ServiceUnavailableError("Сервис заказов недоступен") from error
        if response.is_error and not (allow_not_found and response.status_code == 404):
            raise ServiceUnavailableError(f"Сервис заказов ответил {response.status_code}")
        return response
