"""Скачивает фото товаров с сайта Apple.

Какие фото нужны, написано в каталоге: имя файла — это идентификатор изображения
в CDN Apple плюс .jpg. Уже скачанные файлы пропускаются.

Запуск из корня репозитория: uv run python scripts/download_product_images.py
"""

import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "services/inventory/src/inventory/seed/catalog.json"
TARGET = ROOT / "services/web/src/web/static/products"
CDN = "https://store.storeimages.cdn-apple.com/1/as-images.apple.com/is/{image_id}"
# Квадрат 1000×1000 на белом фоне: одинаковый размер у всех фото в карусели.
PARAMS = {"wid": "1000", "hei": "1000", "fmt": "jpeg", "qlt": "85"}


def image_files() -> set[str]:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    return {
        image
        for product in catalog["products"]
        for color in product["colors"]
        for image in color["images"]
    }


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    missing = sorted(name for name in image_files() if not (TARGET / name).exists())
    # retries: CDN иногда не отвечает, повторное соединение обычно помогает.
    transport = httpx.HTTPTransport(retries=3)
    with httpx.Client(timeout=60, follow_redirects=True, transport=transport) as client:
        for name in missing:
            response = client.get(CDN.format(image_id=name.removesuffix(".jpg")), params=PARAMS)
            response.raise_for_status()
            (TARGET / name).write_bytes(response.content)
            print(f"{name}: {len(response.content) // 1024} КБ")
    print(f"Скачано: {len(missing)}, всего фото: {len(image_files())}")


if __name__ == "__main__":
    main()
