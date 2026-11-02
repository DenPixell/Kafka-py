"""Корзина и выбранный покупатель в подписанной cookie-сессии.

Подпись не даёт подменить содержимое cookie. Сервер корзину не хранит, поэтому
витрина остаётся без своей БД.
"""

from typing import Any

MAX_QUANTITY = 10

# Демо-покупатели для переключателя в шапке: на них удобно показывать антифрод.
BUYERS = {"anna": "Анна", "boris": "Борис", "vera": "Вера", "gleb": "Глеб"}
DEFAULT_BUYER = "anna"

Session = dict[str, Any]


def current_buyer(session: Session) -> str:
    buyer = session.get("buyer")
    return buyer if buyer in BUYERS else DEFAULT_BUYER


def set_buyer(session: Session, buyer: str) -> None:
    if buyer in BUYERS:
        session["buyer"] = buyer


def cart(session: Session) -> dict[str, int]:
    return dict(session.get("cart", {}))


def add_to_cart(session: Session, sku: str) -> None:
    items = cart(session)
    items[sku] = min(items.get(sku, 0) + 1, MAX_QUANTITY)
    session["cart"] = items


def set_quantity(session: Session, sku: str, quantity: int) -> None:
    items = cart(session)
    if quantity <= 0:
        items.pop(sku, None)
    else:
        items[sku] = min(quantity, MAX_QUANTITY)
    session["cart"] = items


def clear_cart(session: Session) -> None:
    session.pop("cart", None)
