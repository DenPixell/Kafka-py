"""Каталог: категории, модели и их конфигурации.

Конфигурация (Variant) — это то, что лежит на складе и что покупают:
у неё свой артикул (SKU), цена и остаток. Модель (Product) объединяет
конфигурации, которые отличаются только памятью и диагональю.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Category:
    slug: str
    name: str


@dataclass(frozen=True)
class Variant:
    sku: str
    storage_gb: int
    screen_inch: Decimal
    price_kopecks: int
    available: int
    note: str | None = None

    @property
    def in_stock(self) -> bool:
        return self.available > 0


@dataclass(frozen=True)
class Product:
    slug: str
    name: str
    category_slug: str
    variants: tuple[Variant, ...]

    @property
    def min_price_kopecks(self) -> int:
        return min(variant.price_kopecks for variant in self.variants)

    @property
    def in_stock(self) -> bool:
        return any(variant.in_stock for variant in self.variants)


@dataclass(frozen=True)
class VariantInfo:
    """Конфигурация вместе с названием модели: для корзины на витрине."""

    product_slug: str
    product_name: str
    variant: Variant
