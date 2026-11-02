"""Проверка репозитория и миграций на настоящем PostgreSQL в Docker."""

import pytest
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.seed.catalog import load_catalog, seed_catalog
from inventory.storage.catalog_repository import PostgresCatalogRepository
from inventory.storage.tables import stock

pytestmark = pytest.mark.integration


async def test_seed_twice_does_not_duplicate(session: AsyncSession) -> None:
    await seed_catalog(session, load_catalog())
    repository = PostgresCatalogRepository(session)

    products = await repository.list_products(None)

    assert len(products) == len(load_catalog().products)


async def test_product_variants_are_sorted_by_screen_then_storage(session: AsyncSession) -> None:
    product = await PostgresCatalogRepository(session).get_product("ipad-pro-m5")

    assert product is not None
    assert [v.sku for v in product.variants][:4] == [
        "ipad-pro-m5-11-256-silver",
        "ipad-pro-m5-11-256-spaceblack",
        "ipad-pro-m5-11-512-silver",
        "ipad-pro-m5-11-512-spaceblack",
    ]
    assert [c.slug for c in product.colors] == ["spaceblack", "silver"]


async def test_available_is_quantity_minus_reserved(session: AsyncSession) -> None:
    await session.execute(
        update(stock).where(stock.c.sku == "macbook-neo-512-silver").values(quantity=3, reserved=2)
    )

    product = await PostgresCatalogRepository(session).get_product("macbook-neo")

    assert product is not None
    assert {v.sku: v.available for v in product.variants}["macbook-neo-512-silver"] == 1


async def test_category_filter_and_existence(session: AsyncSession) -> None:
    repository = PostgresCatalogRepository(session)

    ipads = await repository.list_products("ipad")

    assert {p.category_slug for p in ipads} == {"ipad"}
    assert await repository.category_exists("ipad") is True
    assert await repository.category_exists("watch") is False


async def test_variants_by_sku(session: AsyncSession) -> None:
    found = await PostgresCatalogRepository(session).get_variants(
        ["macbook-neo-512-citrus", "ipad-pro-m5-13-256-spaceblack", "nope"]
    )

    assert {(v.product_name, v.variant.sku, v.variant.note, v.color.name) for v in found} == {
        ("MacBook Neo", "macbook-neo-512-citrus", "с Touch ID", "Цитрус"),
        ("iPad Pro (M5)", "ipad-pro-m5-13-256-spaceblack", None, "Чёрный космос"),
    }
