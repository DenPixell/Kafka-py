"""Наполнение каталога из catalog.json.

В файле цены задаются как у Apple: базовая цена за диагональ плюс доплата
за объём памяти. Из этого собираются конкретные конфигурации (SKU).
Цены вымышленные, в рублях.
"""

from dataclasses import dataclass
from decimal import Decimal
from importlib.resources import files
from typing import Any

from pydantic import BaseModel, Field, PositiveInt
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.storage.tables import categories, product_variants, products, stock

DEFAULT_STOCK = 10


class CategorySeed(BaseModel):
    slug: str
    name: str


class ProductSeed(BaseModel):
    slug: str
    category: str
    name: str
    # диагональ → базовая цена в рублях
    screens: dict[Decimal, PositiveInt] = Field(min_length=1)
    # объём памяти в ГБ → доплата в рублях
    storage: dict[PositiveInt, int] = Field(min_length=1)
    # объём памяти в ГБ → особенность конфигурации («с Touch ID»)
    notes: dict[PositiveInt, str] = {}
    stock: int = Field(default=DEFAULT_STOCK, ge=0)


class CatalogSeed(BaseModel):
    categories: list[CategorySeed]
    products: list[ProductSeed]


@dataclass(frozen=True)
class VariantRow:
    sku: str
    product_slug: str
    storage_gb: int
    screen_inch: Decimal
    price_kopecks: int
    note: str | None
    quantity: int


def load_catalog() -> CatalogSeed:
    raw = files("inventory.seed").joinpath("catalog.json").read_text(encoding="utf-8")
    return CatalogSeed.model_validate_json(raw)


def build_variants(product: ProductSeed) -> list[VariantRow]:
    """Все сочетания диагонали и памяти одной модели."""
    several_screens = len(product.screens) > 1
    rows = []
    for screen, base_price in product.screens.items():
        for storage_gb, surcharge in product.storage.items():
            # Диагональ попадает в артикул, только если у модели их несколько.
            screen_part = f"-{screen:f}".replace(".", "") if several_screens else ""
            rows.append(
                VariantRow(
                    sku=f"{product.slug}{screen_part}-{storage_gb}",
                    product_slug=product.slug,
                    storage_gb=storage_gb,
                    screen_inch=screen,
                    price_kopecks=(base_price + surcharge) * 100,
                    note=product.notes.get(storage_gb),
                    quantity=product.stock,
                )
            )
    return rows


async def seed_catalog(session: AsyncSession, catalog: CatalogSeed) -> None:
    """Добавляет недостающие записи. Существующие не трогает, поэтому повторный
    запуск безопасен и не сбрасывает остатки и резервы."""
    category_rows: list[dict[str, Any]] = [
        {"slug": c.slug, "name": c.name, "position": i} for i, c in enumerate(catalog.categories)
    ]
    product_rows: list[dict[str, Any]] = [
        {"slug": p.slug, "category_slug": p.category, "name": p.name, "position": i}
        for i, p in enumerate(catalog.products)
    ]
    variants = [row for product in catalog.products for row in build_variants(product)]

    await session.execute(insert(categories).values(category_rows).on_conflict_do_nothing())
    await session.execute(insert(products).values(product_rows).on_conflict_do_nothing())
    await session.execute(
        insert(product_variants)
        .values(
            [
                {
                    "sku": v.sku,
                    "product_slug": v.product_slug,
                    "storage_gb": v.storage_gb,
                    "screen_inch": v.screen_inch,
                    "price_kopecks": v.price_kopecks,
                    "note": v.note,
                }
                for v in variants
            ]
        )
        .on_conflict_do_nothing()
    )
    await session.execute(
        insert(stock)
        .values([{"sku": v.sku, "quantity": v.quantity} for v in variants])
        .on_conflict_do_nothing()
    )
