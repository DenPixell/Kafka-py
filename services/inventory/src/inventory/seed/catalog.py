"""Наполнение каталога из catalog.json.

В файле цены задаются как у Apple: базовая цена за диагональ плюс доплата
за объём памяти, цвет на цену не влияет. Из этого собираются конкретные
конфигурации (SKU). Цены вымышленные, в рублях.
"""

from dataclasses import dataclass
from decimal import Decimal
from importlib.resources import files
from typing import Any

from pydantic import BaseModel, Field, PositiveInt
from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import Insert, insert
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.storage.tables import categories, product_colors, product_variants, products, stock

DEFAULT_STOCK = 10


class CategorySeed(BaseModel):
    slug: str
    name: str


class ColorSeed(BaseModel):
    slug: str
    name: str
    hex: str = Field(pattern=r"^#[0-9a-f]{6}$")
    # Файлы в static/products витрины, в порядке показа в карусели.
    images: list[str] = Field(min_length=1)


class ProductSeed(BaseModel):
    slug: str
    category: str
    name: str
    description: str = ""
    # диагональ → базовая цена в рублях
    screens: dict[Decimal, PositiveInt] = Field(min_length=1)
    # объём памяти в ГБ → доплата в рублях
    storage: dict[PositiveInt, int] = Field(min_length=1)
    # объём памяти в ГБ → особенность конфигурации («с Touch ID»)
    notes: dict[PositiveInt, str] = {}
    colors: list[ColorSeed] = Field(min_length=1)
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
    color_slug: str
    price_kopecks: int
    note: str | None
    quantity: int


def load_catalog() -> CatalogSeed:
    raw = files("inventory.seed").joinpath("catalog.json").read_text(encoding="utf-8")
    return CatalogSeed.model_validate_json(raw)


def build_variants(product: ProductSeed) -> list[VariantRow]:
    """Все сочетания диагонали, памяти и цвета одной модели."""
    several_screens = len(product.screens) > 1
    rows = []
    for screen, base_price in product.screens.items():
        # Диагональ попадает в артикул, только если у модели их несколько.
        screen_part = f"-{screen:f}".replace(".", "") if several_screens else ""
        for storage_gb, surcharge in product.storage.items():
            for color in product.colors:
                rows.append(
                    VariantRow(
                        sku=f"{product.slug}{screen_part}-{storage_gb}-{color.slug}",
                        product_slug=product.slug,
                        storage_gb=storage_gb,
                        screen_inch=screen,
                        color_slug=color.slug,
                        price_kopecks=(base_price + surcharge) * 100,
                        note=product.notes.get(storage_gb),
                        quantity=product.stock,
                    )
                )
    return rows


async def seed_catalog(session: AsyncSession, catalog: CatalogSeed) -> None:
    """Добавляет недостающие записи и обновляет описания из файла.

    Названия, описания, цвета, фото и цены берутся из файла при каждом запуске.
    Остатки и резервы — живые данные склада, их повторный запуск не трогает.
    """
    category_rows: list[dict[str, Any]] = [
        {"slug": c.slug, "name": c.name, "position": i} for i, c in enumerate(catalog.categories)
    ]
    product_rows: list[dict[str, Any]] = [
        {
            "slug": p.slug,
            "category_slug": p.category,
            "name": p.name,
            "description": p.description,
            "position": i,
        }
        for i, p in enumerate(catalog.products)
    ]
    variants = [row for product in catalog.products for row in build_variants(product)]

    await session.execute(_upsert(categories, category_rows, ["slug"]))
    await session.execute(_upsert(products, product_rows, ["slug"]))
    await session.execute(
        _upsert(
            product_colors,
            [
                {
                    "product_slug": p.slug,
                    "slug": c.slug,
                    "name": c.name,
                    "hex": c.hex,
                    "position": i,
                    "images": c.images,
                }
                for p in catalog.products
                for i, c in enumerate(p.colors)
            ],
            ["product_slug", "slug"],
        )
    )
    await session.execute(
        _upsert(
            product_variants,
            [
                {
                    "sku": v.sku,
                    "product_slug": v.product_slug,
                    "storage_gb": v.storage_gb,
                    "screen_inch": v.screen_inch,
                    "color_slug": v.color_slug,
                    "price_kopecks": v.price_kopecks,
                    "note": v.note,
                }
                for v in variants
            ],
            ["sku"],
        )
    )
    await session.execute(
        insert(stock)
        .values([{"sku": v.sku, "quantity": v.quantity} for v in variants])
        .on_conflict_do_nothing()
    )


def _upsert(table: Table, rows: list[dict[str, Any]], key: list[str]) -> Insert:
    """INSERT ... ON CONFLICT (key) DO UPDATE: новые строки добавляет, старые обновляет."""
    statement = insert(table).values(rows)
    return statement.on_conflict_do_update(
        index_elements=key,
        set_={column: statement.excluded[column] for column in rows[0] if column not in key},
    )
