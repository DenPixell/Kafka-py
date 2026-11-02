from collections.abc import AsyncIterator

import httpx
import pytest

from web.app import create_app
from web.clients.catalog import CatalogClient
from web.clients.orders import OrderClient
from web.config import Settings

from .backend import FakeBackend

SETTINGS = Settings(
    inventory_url="http://inventory", order_url="http://order", session_secret="test-secret"
)


@pytest.fixture
def backend() -> FakeBackend:
    return FakeBackend()


@pytest.fixture
async def client(backend: FakeBackend) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(SETTINGS)
    async with (
        httpx.AsyncClient(transport=backend.transport(), base_url="http://inventory") as inv,
        httpx.AsyncClient(transport=backend.transport(), base_url="http://order") as orders,
    ):
        # ASGITransport не запускает lifespan, поэтому клиенты к сервисам задаём сами.
        app.state.catalog = CatalogClient(inv)
        app.state.orders = OrderClient(orders)
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://shop") as client:
            yield client
