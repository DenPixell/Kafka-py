from decimal import Decimal

from web.clients.catalog import Product
from web.configurator import configure

from .backend import NEO

PRODUCT = Product.model_validate(NEO)


def test_default_is_first_available_in_palette_order() -> None:
    config = configure(PRODUCT)

    # Серебристый 256 ГБ закончился: берём серебристый 512, а не цитрус по алфавиту.
    assert config.variant.sku == "macbook-neo-512-silver"
    assert config.color.slug == "silver"


def test_changing_color_keeps_storage_when_possible() -> None:
    config = configure(PRODUCT, color="citrus", storage="256")

    assert config.variant.sku == "macbook-neo-256-citrus"


def test_unavailable_combination_is_shown_not_replaced() -> None:
    config = configure(PRODUCT, color="citrus", storage="512")

    assert config.variant.sku == "macbook-neo-512-citrus"
    assert config.variant.in_stock is False


def test_options_know_their_stock_for_current_selection() -> None:
    config = configure(PRODUCT, color="citrus", storage="256")

    assert [(o.label, o.selected, o.in_stock) for o in config.storages] == [
        ("256 ГБ", True, True),
        ("512 ГБ", False, False),
    ]
    assert [(o.label, o.in_stock) for o in config.colors] == [
        ("Серебристый", False),
        ("Цитрус", True),
    ]


def test_option_links_change_one_parameter() -> None:
    config = configure(PRODUCT, color="citrus", storage="256")

    assert config.colors[0].selection.query() == "color=silver&screen=13&storage=256"
    assert config.selection.screen == Decimal("13.0")


def test_garbage_parameters_fall_back_to_defaults() -> None:
    config = configure(PRODUCT, color="purple", screen="abc", storage="-1")

    assert config.variant.sku == "macbook-neo-512-silver"
