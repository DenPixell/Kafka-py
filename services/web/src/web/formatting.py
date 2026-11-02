"""Фильтры для шаблонов: деньги, память, диагональ, статусы."""

from decimal import Decimal

NBSP = " "
THIN_NBSP = " "

ORDER_STATUSES = {
    "NEW": ("Принят", "pending"),
    "RESERVING": ("Резервируем товар", "pending"),
    "FRAUD_CHECK": ("Проверяем заказ", "pending"),
    "CONFIRMED": ("Подтверждён", "success"),
    "CANCELLING": ("Отменяем, возвращаем товар на склад", "pending"),
    "CANCELLED": ("Отменён", "danger"),
}

CANCEL_REASONS = {
    "out_of_stock": "Товара не хватило на складе",
    "fraud": "Заказ не прошёл проверку безопасности",
}

COUNTRIES = {
    "RU": "Россия",
    "BY": "Беларусь",
    "KZ": "Казахстан",
    "AM": "Армения",
    "UZ": "Узбекистан",
    "GE": "Грузия",
}


def money(kopecks: int) -> str:
    rubles = kopecks // 100
    return f"{rubles:,}".replace(",", THIN_NBSP) + f"{NBSP}₽"


def storage(gb: int) -> str:
    if gb >= 1024 and gb % 1024 == 0:
        return f"{gb // 1024}{NBSP}ТБ"
    return f"{gb}{NBSP}ГБ"


def screen(inch: Decimal) -> str:
    return f"{inch.normalize():f}".replace(".", ",") + "″"


def status_label(status: str) -> str:
    return ORDER_STATUSES.get(status, (status, "pending"))[0]


def status_tone(status: str) -> str:
    return ORDER_STATUSES.get(status, (status, "pending"))[1]


def cancel_reason(reason: str | None) -> str:
    return CANCEL_REASONS.get(reason or "", "")


def country(code: str) -> str:
    return COUNTRIES.get(code, code)
