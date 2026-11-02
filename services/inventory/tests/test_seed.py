from decimal import Decimal
from pathlib import Path

from inventory.seed.catalog import ColorSeed, ProductSeed, build_variants, load_catalog

BLACK = ColorSeed(slug="black", name="Чёрный", hex="#232325", images=["black.jpg"])
SILVER = ColorSeed(slug="silver", name="Серебристый", hex="#e2e3e4", images=["silver.jpg"])


def test_variants_are_every_screen_storage_and_color_combination() -> None:
    product = ProductSeed(
        slug="ipad-pro-m5",
        category="ipad",
        name="iPad Pro (M5)",
        screens={Decimal("11"): 100_000, Decimal("13"): 130_000},
        storage={256: 0, 512: 20_000},
        colors=[BLACK, SILVER],
    )

    variants = build_variants(product)

    assert len(variants) == 8
    # Цвет на цену не влияет.
    assert {(v.sku, v.price_kopecks) for v in variants if v.screen_inch == 11} == {
        ("ipad-pro-m5-11-256-black", 10_000_000),
        ("ipad-pro-m5-11-256-silver", 10_000_000),
        ("ipad-pro-m5-11-512-black", 12_000_000),
        ("ipad-pro-m5-11-512-silver", 12_000_000),
    }


def test_single_screen_is_not_in_sku() -> None:
    product = ProductSeed(
        slug="iphone-17",
        category="iphone",
        name="iPhone 17",
        screens={Decimal("6.3"): 80_000},
        storage={256: 0},
        colors=[BLACK],
    )

    assert [v.sku for v in build_variants(product)] == ["iphone-17-256-black"]


def test_shipped_catalog_is_consistent() -> None:
    catalog = load_catalog()
    category_slugs = {c.slug for c in catalog.categories}
    skus = [v.sku for p in catalog.products for v in build_variants(p)]

    assert all(p.category in category_slugs for p in catalog.products)
    assert len(skus) == len(set(skus))


def test_touch_id_only_on_512gb_macbook_neo() -> None:
    neo = next(p for p in load_catalog().products if p.slug == "macbook-neo")

    notes = {(v.storage_gb, v.note) for v in build_variants(neo)}

    assert notes == {(256, None), (512, "с Touch ID")}


def test_iphone_18_pro_comes_in_burgundy() -> None:
    pro = next(p for p in load_catalog().products if p.slug == "iphone-18-pro")

    assert "burgundy" in [c.slug for c in pro.colors]


def test_every_color_has_its_photos_downloaded() -> None:
    photos = Path(__file__).parents[2] / "web/src/web/static/products"
    images = {i for p in load_catalog().products for c in p.colors for i in c.images}

    assert sorted(i for i in images if not (photos / i).exists()) == []
