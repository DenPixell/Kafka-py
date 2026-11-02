from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from inventory.api.schemas import CategoryOut, ProductOut, VariantInfoOut
from inventory.service.catalog import CatalogService
from inventory.storage.catalog_repository import PostgresCatalogRepository

router = APIRouter()


async def get_catalog_service(request: Request) -> AsyncIterator[CatalogService]:
    """Сервис на один запрос: своя сессия БД, закрывается после ответа."""
    async with request.app.state.session_factory() as session:
        yield CatalogService(PostgresCatalogRepository(session))


Catalog = Annotated[CatalogService, Depends(get_catalog_service)]


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/categories")
async def list_categories(catalog: Catalog) -> list[CategoryOut]:
    return [CategoryOut.from_domain(c) for c in await catalog.list_categories()]


@router.get("/products")
async def list_products(catalog: Catalog, category: str | None = None) -> list[ProductOut]:
    """Модели с конфигурациями: на витрине память и цвет выбираются прямо в каталоге."""
    return [ProductOut.from_domain(p) for p in await catalog.list_products(category)]


@router.get("/products/{slug}")
async def get_product(catalog: Catalog, slug: str) -> ProductOut:
    return ProductOut.from_domain(await catalog.get_product(slug))


@router.get("/variants")
async def get_variants(
    catalog: Catalog, sku: Annotated[list[str], Query(min_length=1, max_length=50)]
) -> list[VariantInfoOut]:
    """Конфигурации по артикулам: /variants?sku=a&sku=b."""
    return [VariantInfoOut.from_info(v) for v in await catalog.get_variants(sku)]
