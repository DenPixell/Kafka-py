from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pytest

from order.api.app import create_app
from order.api.routes import get_order_service
from order.config import Settings
from order.service.orders import OrderService

ANNA = {"X-User-Id": "anna"}
BODY = {"items": [{"sku": "iphone-17-256", "quantity": 1}], "delivery_country": "RU"}


@pytest.fixture
async def client(service: OrderService) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(Settings(database_url="postgresql+asyncpg://user:pass@localhost/test"))
    app.dependency_overrides[get_order_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_create_order_returns_202_and_status(client: httpx.AsyncClient) -> None:
    response = await client.post("/orders", json=BODY, headers=ANNA)

    assert response.status_code == 202
    assert response.json()["status"] == "RESERVING"
    assert response.json()["total_kopecks"] is None


async def test_created_order_can_be_read_by_owner_only(client: httpx.AsyncClient) -> None:
    order_id = (await client.post("/orders", json=BODY, headers=ANNA)).json()["id"]

    own = await client.get(f"/orders/{order_id}", headers=ANNA)
    foreign = await client.get(f"/orders/{order_id}", headers={"X-User-Id": "boris"})

    assert own.status_code == 200
    assert foreign.status_code == 404


async def test_user_id_header_is_required(client: httpx.AsyncClient) -> None:
    response = await client.post("/orders", json=BODY)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {**BODY, "items": []},
        {**BODY, "delivery_country": "Russia"},
        {**BODY, "items": [{"sku": "iphone-17-256", "quantity": 0}]},
        {**BODY, "items": [{"sku": "a", "quantity": 1}, {"sku": "a", "quantity": 2}]},
        {**BODY, "user_id": "boris"},
    ],
    ids=["no-items", "bad-country", "zero-quantity", "duplicate-sku", "user-id-in-body"],
)
async def test_invalid_body_is_rejected(client: httpx.AsyncClient, body: dict[str, object]) -> None:
    response = await client.post("/orders", json=body, headers=ANNA)

    assert response.status_code == 422


async def test_unknown_order_is_404(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/orders/{uuid4()}", headers=ANNA)

    assert response.status_code == 404


async def test_list_shows_only_own_orders_newest_first(client: httpx.AsyncClient) -> None:
    first = (await client.post("/orders", json=BODY, headers=ANNA)).json()["id"]
    second = (await client.post("/orders", json=BODY, headers=ANNA)).json()["id"]
    await client.post("/orders", json=BODY, headers={"X-User-Id": "boris"})

    response = await client.get("/orders", headers=ANNA)

    assert [o["id"] for o in response.json()] == [second, first]
