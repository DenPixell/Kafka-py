"""Формат ответов HTTP API. Отделён от доменных классов, чтобы менять API
и домен независимо друг от друга."""

from decimal import Decimal

from pydantic import BaseModel

from inventory.domain.catalog import Category, Product, Variant, VariantInfo


class CategoryOut(BaseModel):
    slug: str
    name: str

    @classmethod
    def from_domain(cls, category: Category) -> "CategoryOut":
        return cls(slug=category.slug, name=category.name)


class ProductSummaryOut(BaseModel):
    slug: str
    name: str
    category_slug: str
    min_price_kopecks: int
    in_stock: bool

    @classmethod
    def from_domain(cls, product: Product) -> "ProductSummaryOut":
        return cls(
            slug=product.slug,
            name=product.name,
            category_slug=product.category_slug,
            min_price_kopecks=product.min_price_kopecks,
            in_stock=product.in_stock,
        )


class VariantOut(BaseModel):
    sku: str
    storage_gb: int
    # Диагональ строкой («6.3»): точное значение без погрешностей float.
    screen_inch: Decimal
    price_kopecks: int
    available: int
    note: str | None

    @classmethod
    def from_domain(cls, variant: Variant) -> "VariantOut":
        return cls(
            sku=variant.sku,
            storage_gb=variant.storage_gb,
            screen_inch=variant.screen_inch,
            price_kopecks=variant.price_kopecks,
            available=variant.available,
            note=variant.note,
        )


class ProductOut(ProductSummaryOut):
    variants: list[VariantOut]

    @classmethod
    def from_domain(cls, product: Product) -> "ProductOut":
        summary = ProductSummaryOut.from_domain(product)
        return cls(
            **summary.model_dump(),
            variants=[VariantOut.from_domain(v) for v in product.variants],
        )


class VariantInfoOut(VariantOut):
    product_slug: str
    product_name: str
    category_slug: str

    @classmethod
    def from_info(cls, info: VariantInfo) -> "VariantInfoOut":
        return cls(
            **VariantOut.from_domain(info.variant).model_dump(),
            product_slug=info.product_slug,
            product_name=info.product_name,
            category_slug=info.category_slug,
        )
