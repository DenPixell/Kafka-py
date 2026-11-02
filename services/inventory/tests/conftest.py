from decimal import Decimal

import pytest

from inventory.domain.catalog import Category, Product, Variant


class FakeCatalogRepository:
    """Хранилище в памяти: тесты сервиса и API работают без базы."""

    def __init__(self, categories: list[Category], products: list[Product]) -> None:
        self._categories = categories
        self._products = products

    async def list_categories(self) -> list[Category]:
        return self._categories

    async def category_exists(self, slug: str) -> bool:
        return any(c.slug == slug for c in self._categories)

    async def list_products(self, category_slug: str | None) -> list[Product]:
        return [p for p in self._products if category_slug in (None, p.category_slug)]

    async def get_product(self, slug: str) -> Product | None:
        return next((p for p in self._products if p.slug == slug), None)


def make_variant(sku: str, price_kopecks: int, available: int = 5) -> Variant:
    return Variant(
        sku=sku,
        storage_gb=256,
        screen_inch=Decimal("6.3"),
        price_kopecks=price_kopecks,
        available=available,
    )


@pytest.fixture
def repository() -> FakeCatalogRepository:
    return FakeCatalogRepository(
        categories=[Category("iphone", "iPhone"), Category("mac", "MacBook")],
        products=[
            Product(
                slug="iphone-17",
                name="iPhone 17",
                category_slug="iphone",
                variants=(
                    make_variant("iphone-17-256", 7_999_000),
                    make_variant("iphone-17-512", 9_999_000, available=0),
                ),
            ),
            Product(
                slug="macbook-neo",
                name="MacBook Neo",
                category_slug="mac",
                variants=(make_variant("macbook-neo-256", 6_999_000, available=0),),
            ),
        ],
    )
