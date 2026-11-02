"""Результат попытки отложить товары под заказ."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RequestedLine:
    sku: str
    quantity: int


@dataclass(frozen=True)
class ReservedLine:
    sku: str
    quantity: int
    unit_price_kopecks: int


@dataclass(frozen=True)
class Reserved:
    lines: tuple[ReservedLine, ...]

    @property
    def total_kopecks(self) -> int:
        return sum(line.quantity * line.unit_price_kopecks for line in self.lines)


@dataclass(frozen=True)
class Unavailable:
    """Хотя бы одной позиции не хватило: не отложено ничего."""

    skus: tuple[str, ...]


ReservationResult = Reserved | Unavailable
