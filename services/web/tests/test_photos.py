"""Фото в карусели не должны повторяться.

Apple иногда отдаёт один и тот же кадр под разными идентификаторами (например,
основное фото и «_AV1»), а файлы при этом отличаются байтами из-за сжатия.
Поэтому сравниваем не файлы, а уменьшенные чёрно-белые копии изображений.
"""

import json
from itertools import combinations
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageStat

ROOT = Path(__file__).resolve().parents[3]
PHOTOS = ROOT / "services/web/src/web/static/products"
CATALOG = json.loads(
    (ROOT / "services/inventory/src/inventory/seed/catalog.json").read_text(encoding="utf-8")
)
# Средняя разница яркости меньше 3 из 255 — для глаза это один и тот же кадр.
SAME_PICTURE = 3.0

COLORS = [
    pytest.param(color["images"], id=f"{product['slug']}-{color['slug']}")
    for product in CATALOG["products"]
    for color in product["colors"]
]


def thumbnail(name: str) -> Image.Image:
    return Image.open(PHOTOS / name).convert("L").resize((64, 64))


@pytest.mark.parametrize("images", COLORS)
def test_photos_of_one_color_are_different(images: list[str]) -> None:
    thumbs = {name: thumbnail(name) for name in images}

    duplicates = [
        (a, b)
        for a, b in combinations(images, 2)
        if ImageStat.Stat(ImageChops.difference(thumbs[a], thumbs[b])).mean[0] < SAME_PICTURE
    ]

    assert duplicates == []
