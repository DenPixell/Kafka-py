"""Поддельные inventory и order на уровне HTTP: витрина ходит в них настоящим httpx."""

import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

SILVER = {
    "slug": "silver",
    "name": "Серебристый",
    "hex": "#e2e3e4",
    "images": ["neo-silver-1.jpg", "neo-silver-2.jpg"],
}
CITRUS = {"slug": "citrus", "name": "Цитрус", "hex": "#e5df88", "images": ["neo-citrus-1.jpg"]}


def variant(
    storage: int, color: str, price: int, available: int, note: str | None = None
) -> dict[str, Any]:
    return {
        "sku": f"macbook-neo-{storage}-{color}",
        "storage_gb": storage,
        "screen_inch": "13.0",
        "color_slug": color,
        "price_kopecks": price,
        "available": available,
        "note": note,
    }


NEO_VARIANTS = [
    variant(256, "silver", 6_999_000, 0),
    variant(256, "citrus", 6_999_000, 3),
    variant(512, "silver", 7_999_000, 4, "с Touch ID"),
    variant(512, "citrus", 7_999_000, 0, "с Touch ID"),
]
NEO = {
    "slug": "macbook-neo",
    "name": "MacBook Neo",
    "description": "Самый доступный MacBook",
    "category_slug": "mac",
    "min_price_kopecks": 6_999_000,
    "in_stock": True,
    "colors": [SILVER, CITRUS],
    "variants": NEO_VARIANTS,
}
COLORS = {"silver": SILVER, "citrus": CITRUS}


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
            return httpx.Response(200, json=NEO)
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
                        "color": COLORS[v["color_slug"]],
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
