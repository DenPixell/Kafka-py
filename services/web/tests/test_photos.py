"""Фото в карусели не должны повторяться.

Apple иногда отдаёт один и тот же кадр под разными идентификаторами (например,
основное фото и «_AV1»), а файлы при этом отличаются байтами из-за сжатия.
Бывает и тот же ракурс в другом масштабе: MacBook Air 13″ и 15″ спереди.
Поэтому сравниваем не файлы, а сам предмет: обрезаем светлый фон, приводим
к одному размеру и сравниваем чёрно-белые копии.
"""

import json
from itertools import combinations
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageFilter, ImageStat

ROOT = Path(__file__).resolve().parents[3]
PHOTOS = ROOT / "services/web/src/web/static/products"
CATALOG = json.loads(
    (ROOT / "services/inventory/src/inventory/seed/catalog.json").read_text(encoding="utf-8")
)
# Порог подобран на реальных фото: повторы дают 2–7 из 255, разные ракурсы — от 10.
SAME_PICTURE = 8.0

COLORS = [
    pytest.param(color["images"], id=f"{product['slug']}-{color['slug']}")
    for product in CATALOG["products"]
    for color in product["colors"]
]


def thumbnail(name: str) -> Image.Image:
    return normalized(Image.open(PHOTOS / name))


def normalized(image: Image.Image) -> Image.Image:
    gray = image.convert("L")
    # Всё темнее почти белого — это предмет. Обрезаем фон вокруг него.
    content = gray.point(lambda value: 255 if value < 235 else 0).getbbox()
    subject = gray.crop(content) if content else gray
    # Крупная сетка и лёгкое размытие: мелкие сдвиги и сжатие не мешают сравнению.
    return subject.resize((16, 16)).filter(ImageFilter.GaussianBlur(1))


@pytest.mark.parametrize("images", COLORS)
def test_photos_of_one_color_are_different(images: list[str]) -> None:
    thumbs = {name: thumbnail(name) for name in images}

    duplicates = [
        (a, b)
        for a, b in combinations(images, 2)
        if ImageStat.Stat(ImageChops.difference(thumbs[a], thumbs[b])).mean[0] < SAME_PICTURE
    ]

    assert duplicates == []
