"""HTTP-клиент каталога inventory. Модели повторяют ответы его API."""

from decimal import Decimal

import httpx
from pydantic import BaseModel, TypeAdapter

from web.clients.errors import ServiceUnavailableError


class Category(BaseModel):
    slug: str
    name: str


class Color(BaseModel):
    slug: str
    name: str
    hex: str
    images: list[str]


class Variant(BaseModel):
    sku: str
    storage_gb: int
    screen_inch: Decimal
    color_slug: str
    price_kopecks: int
    available: int
    note: str | None

    @property
    def in_stock(self) -> bool:
        return self.available > 0


class Product(BaseModel):
    slug: str
    name: str
    description: str
    category_slug: str
    min_price_kopecks: int
    in_stock: bool
    colors: list[Color]
    variants: list[Variant]


class VariantInfo(Variant):
    product_slug: str
    product_name: str
    category_slug: str
    color: Color


_categories = TypeAdapter(list[Category])
_products = TypeAdapter(list[Product])
_variants = TypeAdapter(list[VariantInfo])


class CatalogClient:
    def __init__(self, http: httpx.AsyncClient) -> None:
        self._http = http

    async def categories(self) -> list[Category]:
        response = await self._get("/categories")
        return _categories.validate_json(response.content)

    async def products(self, category: str | None = None) -> list[Product] | None:
        """None — такой категории нет."""
        response = await self._get("/products", {"category": category} if category else None)
        if response.status_code == 404:
            return None
        return _products.validate_json(response.content)

    async def product(self, slug: str) -> Product | None:
        response = await self._get(f"/products/{slug}")
        if response.status_code == 404:
            return None
        return Product.model_validate_json(response.content)

    async def variants(self, skus: list[str]) -> list[VariantInfo]:
        if not skus:
            return []
        response = await self._get("/variants", {"sku": skus})
        return _variants.validate_json(response.content)

    async def _get(
        self, path: str, params: dict[str, str | list[str]] | None = None
    ) -> httpx.Response:
        """Ответ 200 или 404. Остальное — сервис недоступен."""
        try:
            response = await self._http.get(path, params=params)
        except httpx.HTTPError as error:
            raise ServiceUnavailableError("Каталог недоступен") from error
        if response.is_error and response.status_code != 404:
            raise ServiceUnavailableError(f"Каталог ответил {response.status_code}")
        return response
