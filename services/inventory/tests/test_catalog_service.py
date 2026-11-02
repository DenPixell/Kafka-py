import pytest

from inventory.domain.errors import CategoryNotFoundError, ProductNotFoundError
from inventory.service.catalog import CatalogRepository, CatalogService


async def test_list_products_filters_by_category(repository: CatalogRepository) -> None:
    service = CatalogService(repository)

    products = await service.list_products("mac")

    assert [p.slug for p in products] == ["macbook-neo"]


async def test_unknown_category_is_an_error(repository: CatalogRepository) -> None:
    service = CatalogService(repository)

    with pytest.raises(CategoryNotFoundError):
        await service.list_products("watch")


async def test_unknown_product_raises(repository: CatalogRepository) -> None:
    service = CatalogService(repository)

    with pytest.raises(ProductNotFoundError):
        await service.get_product("iphone-99")


async def test_product_price_and_stock_come_from_variants(repository: CatalogRepository) -> None:
    service = CatalogService(repository)

    iphone = await service.get_product("iphone-17")
    neo = await service.get_product("macbook-neo")

    assert iphone.min_price_kopecks == 7_999_000
    assert iphone.in_stock is True
    assert neo.in_stock is False
