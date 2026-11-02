"""Выбор конфигурации: цвет, диагональ и память → конкретный артикул.

Покупатель меняет один параметр, остальные сохраняются. Каждая кнопка выбора
знает, есть ли такая конфигурация в наличии, чтобы витрина могла её приглушить.
Логика здесь, а не в шаблоне: так её можно проверить тестами.
"""

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation

from web.clients.catalog import Color, Product, Variant
from web.formatting import screen as screen_label
from web.formatting import storage as storage_label


@dataclass(frozen=True)
class Selection:
    color: str
    screen: Decimal
    storage: int

    def query(self) -> str:
        return f"color={self.color}&screen={self.screen.normalize():f}&storage={self.storage}"


@dataclass(frozen=True)
class Option:
    label: str
    selected: bool
    in_stock: bool
    selection: Selection
    hex: str | None = None


@dataclass(frozen=True)
class Configuration:
    product: Product
    selection: Selection
    variant: Variant
    color: Color
    colors: list[Option]
    screens: list[Option]
    storages: list[Option]


def configure(
    product: Product,
    color: str | None = None,
    screen: str | None = None,
    storage: str | None = None,
) -> Configuration:
    selection = _resolve(product, color, _decimal(screen), _int(storage))
    variants = {(v.color_slug, v.screen_inch, v.storage_gb): v for v in product.variants}

    def option(label: str, candidate: Selection, hex_: str | None = None) -> Option:
        variant = variants.get((candidate.color, candidate.screen, candidate.storage))
        return Option(
            label=label,
            selected=candidate == selection,
            in_stock=variant is not None and variant.in_stock,
            selection=candidate,
            hex=hex_,
        )

    screens = sorted({v.screen_inch for v in product.variants})
    storages = sorted({v.storage_gb for v in product.variants})
    return Configuration(
        product=product,
        selection=selection,
        variant=variants[(selection.color, selection.screen, selection.storage)],
        color=next(c for c in product.colors if c.slug == selection.color),
        colors=[option(c.name, replace(selection, color=c.slug), c.hex) for c in product.colors],
        screens=[option(screen_label(s), replace(selection, screen=s)) for s in screens],
        storages=[option(storage_label(s), replace(selection, storage=s)) for s in storages],
    )


def _resolve(
    product: Product, color: str | None, screen: Decimal | None, storage: int | None
) -> Selection:
    """Запрошенные параметры, а где их нет или они неверные — первая конфигурация
    в наличии, подходящая под уже выбранное. Если в наличии ничего — просто первая."""
    candidates = [
        v
        for v in product.variants
        if (color is None or v.color_slug == color)
        and (screen is None or v.screen_inch == screen)
        and (storage is None or v.storage_gb == storage)
    ] or product.variants
    # Цвета перебираем в порядке палитры модели, а не по алфавиту артикулов.
    palette = [c.slug for c in product.colors]
    candidates = sorted(candidates, key=lambda v: palette.index(v.color_slug))
    best = next((v for v in candidates if v.in_stock), candidates[0])
    return Selection(color=best.color_slug, screen=best.screen_inch, storage=best.storage_gb)


def _decimal(value: str | None) -> Decimal | None:
    try:
        return Decimal(value) if value else None
    except InvalidOperation:
        return None


def _int(value: str | None) -> int | None:
    return int(value) if value and value.isdigit() else None
