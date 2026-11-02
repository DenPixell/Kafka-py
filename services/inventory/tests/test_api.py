from collections.abc import AsyncIterator

import httpx
import pytest

from inventory.api.app import create_app
from inventory.api.routes import get_catalog_service
from inventory.config import Settings
from inventory.service.catalog import CatalogRepository, CatalogService


@pytest.fixture
async def client(repository: CatalogRepository) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(Settings(database_url="postgresql+asyncpg://user:pass@localhost/test"))
    app.dependency_overrides[get_catalog_service] = lambda: CatalogService(repository)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_categories(client: httpx.AsyncClient) -> None:
    response = await client.get("/categories")

    assert response.status_code == 200
    assert [c["slug"] for c in response.json()] == ["iphone", "mac"]


async def test_products_by_category(client: httpx.AsyncClient) -> None:
    response = await client.get("/products", params={"category": "iphone"})

    assert response.status_code == 200
    [product] = response.json()
    assert product["slug"] == "iphone-17"
    assert product["min_price_kopecks"] == 7_999_000
    assert product["in_stock"] is True
    assert product["description"] == "Базовая модель"
    assert [v["sku"] for v in product["variants"]] == ["iphone-17-256", "iphone-17-512"]
    assert product["colors"] == [
        {
            "slug": "black",
            "name": "Чёрный",
            "hex": "#232325",
            "images": ["black-1.jpg", "black-2.jpg"],
        }
    ]


async def test_product_with_variants(client: httpx.AsyncClient) -> None:
    response = await client.get("/products/iphone-17")

    body = response.json()
    assert response.status_code == 200
    assert [v["sku"] for v in body["variants"]] == ["iphone-17-256", "iphone-17-512"]
    assert body["variants"][0]["screen_inch"] == "6.3"


@pytest.mark.parametrize("url", ["/products/iphone-99", "/products?category=watch"])
async def test_not_found_is_404(client: httpx.AsyncClient, url: str) -> None:
    response = await client.get(url)

    assert response.status_code == 404


async def test_variants_by_sku_skip_unknown(client: httpx.AsyncClient) -> None:
    response = await client.get(
        "/variants", params=[("sku", "iphone-17-512"), ("sku", "nope"), ("sku", "macbook-neo-256")]
    )

    assert response.status_code == 200
    assert [(v["sku"], v["product_name"], v["color"]["name"]) for v in response.json()] == [
        ("iphone-17-512", "iPhone 17", "Чёрный"),
        ("macbook-neo-256", "MacBook Neo", "Чёрный"),
    ]


async def test_variants_need_at_least_one_sku(client: httpx.AsyncClient) -> None:
    response = await client.get("/variants")

    assert response.status_code == 422
