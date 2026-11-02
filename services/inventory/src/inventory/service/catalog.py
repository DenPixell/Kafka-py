from typing import Protocol

from inventory.domain.catalog import Category, Product, VariantInfo
from inventory.domain.errors import CategoryNotFoundError, ProductNotFoundError


class CatalogRepository(Protocol):
    """То, что сервису нужно от хранилища. Реализация — в inventory.storage."""

    async def list_categories(self) -> list[Category]: ...

    async def category_exists(self, slug: str) -> bool: ...

    async def list_products(self, category_slug: str | None) -> list[Product]: ...

    async def get_product(self, slug: str) -> Product | None: ...

    async def get_variants(self, skus: list[str]) -> list[VariantInfo]: ...


class CatalogService:
    def __init__(self, repository: CatalogRepository) -> None:
        self._repository = repository

    async def list_categories(self) -> list[Category]:
        return await self._repository.list_categories()

    async def list_products(self, category_slug: str | None = None) -> list[Product]:
        if category_slug is not None and not await self._repository.category_exists(category_slug):
            raise CategoryNotFoundError(category_slug)
        return await self._repository.list_products(category_slug)

    async def get_product(self, slug: str) -> Product:
        product = await self._repository.get_product(slug)
        if product is None:
            raise ProductNotFoundError(slug)
        return product

    async def get_variants(self, skus: list[str]) -> list[VariantInfo]:
        """Неизвестные артикулы просто не попадают в ответ."""
        return await self._repository.get_variants(skus)
