from decimal import Decimal

import pytest

from web.formatting import money, screen, storage


def test_money_groups_thousands_and_drops_kopecks() -> None:
    assert money(58_999_000) == "589 990 ₽"


@pytest.mark.parametrize(("gb", "text"), [(256, "256 ГБ"), (1024, "1 ТБ"), (8192, "8 ТБ")])
def test_storage(gb: int, text: str) -> None:
    assert storage(gb) == text


@pytest.mark.parametrize(("inch", "text"), [("6.3", "6,3″"), ("13.0", "13″"), ("10.9", "10,9″")])
def test_screen(inch: str, text: str) -> None:
    assert screen(Decimal(inch)) == text
