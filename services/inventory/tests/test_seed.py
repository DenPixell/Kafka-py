from decimal import Decimal

from inventory.seed.catalog import ProductSeed, build_variants, load_catalog


def test_variants_are_every_screen_and_storage_combination() -> None:
    product = ProductSeed(
        slug="ipad-pro-m5",
        category="ipad",
        name="iPad Pro (M5)",
        screens={Decimal("11"): 100_000, Decimal("13"): 130_000},
        storage={256: 0, 512: 20_000},
    )

    variants = build_variants(product)

    assert {(v.sku, v.price_kopecks) for v in variants} == {
        ("ipad-pro-m5-11-256", 10_000_000),
        ("ipad-pro-m5-11-512", 12_000_000),
        ("ipad-pro-m5-13-256", 13_000_000),
        ("ipad-pro-m5-13-512", 15_000_000),
    }


def test_single_screen_is_not_in_sku() -> None:
    product = ProductSeed(
        slug="iphone-17",
        category="iphone",
        name="iPhone 17",
        screens={Decimal("6.3"): 80_000},
        storage={256: 0},
    )

    assert [v.sku for v in build_variants(product)] == ["iphone-17-256"]


def test_shipped_catalog_is_consistent() -> None:
    catalog = load_catalog()
    category_slugs = {c.slug for c in catalog.categories}
    skus = [v.sku for p in catalog.products for v in build_variants(p)]

    assert all(p.category in category_slugs for p in catalog.products)
    assert len(skus) == len(set(skus))


def test_touch_id_only_on_512gb_macbook_neo() -> None:
    neo = next(p for p in load_catalog().products if p.slug == "macbook-neo")

    notes = {v.storage_gb: v.note for v in build_variants(neo)}

    assert notes == {256: None, 512: "с Touch ID"}
