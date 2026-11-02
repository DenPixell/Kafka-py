"""Каталог: категории, модели и их конфигурации.

Конфигурация (Variant) — это то, что лежит на складе и что покупают:
у неё свой артикул (SKU), цена и остаток. Модель (Product) объединяет
конфигурации, которые отличаются памятью, диагональю и цветом.
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Category:
    slug: str
    name: str


@dataclass(frozen=True)
class Color:
    """Цвет корпуса модели. У каждой модели своя палитра и свои фото."""

    slug: str
    name: str
    hex: str
    images: tuple[str, ...]


@dataclass(frozen=True)
class Variant:
    sku: str
    storage_gb: int
    screen_inch: Decimal
    color_slug: str
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
    description: str
    category_slug: str
    colors: tuple[Color, ...]
    variants: tuple[Variant, ...]

    @property
    def min_price_kopecks(self) -> int:
        return min(variant.price_kopecks for variant in self.variants)

    @property
    def in_stock(self) -> bool:
        return any(variant.in_stock for variant in self.variants)

    def color(self, slug: str) -> Color:
        return next(color for color in self.colors if color.slug == slug)


@dataclass(frozen=True)
class VariantInfo:
    """Конфигурация вместе с моделью и цветом: для корзины и заказа на витрине."""

    product_slug: str
    product_name: str
    category_slug: str
    color: Color
    variant: Variant
