from uuid import uuid4

import pytest
from pydantic import ValidationError

from contracts import OrderLine, ReserveStock


def test_reserve_stock_has_fixed_type() -> None:
    command = ReserveStock(order_id=uuid4(), lines=(OrderLine(sku="iphone-17-256", quantity=1),))

    assert command.type == "ReserveStock"


def test_reserve_stock_needs_at_least_one_line() -> None:
    with pytest.raises(ValidationError):
        ReserveStock(order_id=uuid4(), lines=())


def test_quantity_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        OrderLine(sku="iphone-17-256", quantity=0)
