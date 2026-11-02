from collections.abc import Sequence

from sqlalchemy import Row, Select, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from inventory.domain.catalog import Category, Color, Product, Variant, VariantInfo
from inventory.storage.tables import (
    categories,
    product_colors,
    product_variants,
    products,
    stock,
)


class PostgresCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_categories(self) -> list[Category]:
        result = await self._session.execute(
            select(categories.c.slug, categories.c.name).order_by(categories.c.position)
        )
        return [Category(slug=row.slug, name=row.name) for row in result]

    async def category_exists(self, slug: str) -> bool:
        query = select(exists().where(categories.c.slug == slug))
        return bool(await self._session.scalar(query))

    async def list_products(self, category_slug: str | None) -> list[Product]:
        query = _products_with_variants()
        if category_slug is not None:
            query = query.where(products.c.category_slug == category_slug)
        result = await self._session.execute(query)
        return await self._assemble(result.all())

    async def get_product(self, slug: str) -> Product | None:
        result = await self._session.execute(
            _products_with_variants().where(products.c.slug == slug)
        )
        found = await self._assemble(result.all())
        return found[0] if found else None

    async def get_variants(self, skus: list[str]) -> list[VariantInfo]:
        result = await self._session.execute(
            _products_with_variants().where(product_variants.c.sku.in_(skus))
        )
        return [
            VariantInfo(
                product_slug=product.slug,
                product_name=product.name,
                category_slug=product.category_slug,
                color=product.color(variant.color_slug),
                variant=variant,
            )
            for product in await self._assemble(result.all())
            for variant in product.variants
        ]

    async def _assemble(self, rows: Sequence[Row[tuple[object, ...]]]) -> list[Product]:
        """Строки идут отсортированными по модели, собираем их в модели с цветами."""
        colors = await self._colors({row.slug for row in rows})
        grouped: dict[str, tuple[Row[tuple[object, ...]], list[Variant]]] = {}
        for row in rows:
            _, variants = grouped.setdefault(row.slug, (row, []))
            variants.append(
                Variant(
                    sku=row.sku,
                    storage_gb=row.storage_gb,
                    screen_inch=row.screen_inch,
                    color_slug=row.color_slug,
                    price_kopecks=row.price_kopecks,
                    available=row.available,
                    note=row.note,
                )
            )
        return [
            Product(
                slug=first.slug,
                name=first.name,
                description=first.description,
                category_slug=first.category_slug,
                colors=colors[first.slug],
                variants=tuple(variants),
            )
            for first, variants in grouped.values()
        ]

    async def _colors(self, product_slugs: set[str]) -> dict[str, tuple[Color, ...]]:
        result = await self._session.execute(
            select(product_colors)
            .where(product_colors.c.product_slug.in_(product_slugs))
            .order_by(product_colors.c.product_slug, product_colors.c.position)
        )
        colors: dict[str, list[Color]] = {slug: [] for slug in product_slugs}
        for row in result:
            colors[row.product_slug].append(
                Color(slug=row.slug, name=row.name, hex=row.hex, images=tuple(row.images))
            )
        return {slug: tuple(found) for slug, found in colors.items()}


def _products_with_variants() -> Select[tuple[object, ...]]:
    return (
        select(
            products.c.slug,
            products.c.name,
            products.c.description,
            products.c.category_slug,
            product_variants.c.sku,
            product_variants.c.storage_gb,
            product_variants.c.screen_inch,
            product_variants.c.color_slug,
            product_variants.c.price_kopecks,
            product_variants.c.note,
            (stock.c.quantity - stock.c.reserved).label("available"),
        )
        .join(product_variants, product_variants.c.product_slug == products.c.slug)
        .join(stock, stock.c.sku == product_variants.c.sku)
        .order_by(
            products.c.position,
            product_variants.c.screen_inch,
            product_variants.c.storage_gb,
            product_variants.c.color_slug,
        )
    )
