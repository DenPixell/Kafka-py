"""Поддельные inventory и order на уровне HTTP: витрина ходит в них настоящим httpx."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

NEO = {
    "slug": "macbook-neo",
    "name": "MacBook Neo",
    "category_slug": "mac",
    "min_price_kopecks": 6_999_000,
    "in_stock": True,
}
NEO_VARIANTS = [
    {
        "sku": "macbook-neo-256",
        "storage_gb": 256,
        "screen_inch": "13.0",
        "price_kopecks": 6_999_000,
        "available": 0,
        "note": None,
    },
    {
        "sku": "macbook-neo-512",
        "storage_gb": 512,
        "screen_inch": "13.0",
        "price_kopecks": 7_999_000,
        "available": 4,
        "note": "с Touch ID",
    },
]


class FakeBackend:
    def __init__(self) -> None:
        self.orders: dict[str, dict[str, Any]] = {}
        self.created: list[tuple[str, dict[str, Any]]] = []
        self.down = False

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("connection refused", request=request)
        path, user = request.url.path, request.headers.get("X-User-Id")
        if path == "/categories":
            return httpx.Response(200, json=[{"slug": "mac", "name": "MacBook"}])
        if path == "/products":
            if request.url.params.get("category") not in (None, "mac"):
                return httpx.Response(404, json={"detail": "нет"})
            return httpx.Response(200, json=[NEO])
        if path == "/products/macbook-neo":
            return httpx.Response(200, json={**NEO, "variants": NEO_VARIANTS})
        if path == "/variants":
            skus = request.url.params.get_list("sku")
            return httpx.Response(
                200,
                json=[
                    {
                        **v,
                        "product_slug": "macbook-neo",
                        "product_name": "MacBook Neo",
                        "category_slug": "mac",
                    }
                    for v in NEO_VARIANTS
                    if v["sku"] in skus
                ],
            )
        if path == "/orders" and request.method == "POST":
            body = json.loads(request.content)
            self.created.append((user or "", body))
            order = {
                "id": str(uuid4()),
                "status": "RESERVING",
                "user": user,
                "delivery_country": body["delivery_country"],
                "items": body["items"],
                "total_kopecks": None,
                "cancel_reason": None,
                "created_at": datetime(2026, 11, 2, 12, tzinfo=UTC).isoformat(),
            }
            self.orders[order["id"]] = order
            return httpx.Response(202, json=order)
        if path == "/orders":
            return httpx.Response(200, json=[o for o in self.orders.values() if o["user"] == user])
        if path.startswith("/orders/"):
            found = self.orders.get(path.removeprefix("/orders/"))
            if found is None or found["user"] != user:
                return httpx.Response(404, json={"detail": "нет"})
            return httpx.Response(200, json=found)
        return httpx.Response(404)
