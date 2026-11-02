from uuid import uuid4

import pytest
from pydantic import ValidationError

from contracts import (
    OrderLine,
    PricedLine,
    ReleaseStock,
    ReserveStock,
    StockReserved,
    inventory_commands,
    inventory_events,
)


def test_reserve_stock_has_fixed_type() -> None:
    command = ReserveStock(order_id=uuid4(), lines=(OrderLine(sku="iphone-17-256", quantity=1),))

    assert command.type == "ReserveStock"


def test_reserve_stock_needs_at_least_one_line() -> None:
    with pytest.raises(ValidationError):
        ReserveStock(order_id=uuid4(), lines=())


def test_quantity_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        OrderLine(sku="iphone-17-256", quantity=0)


def test_command_is_parsed_into_its_class_by_type() -> None:
    sent = ReleaseStock(order_id=uuid4())

    received = inventory_commands.validate_json(sent.model_dump_json())

    assert isinstance(received, ReleaseStock)
    assert received == sent


def test_event_is_parsed_into_its_class_by_type() -> None:
    sent = StockReserved(
        order_id=uuid4(),
        lines=(PricedLine(sku="macbook-neo-512", quantity=2, unit_price_kopecks=7_999_000),),
        total_kopecks=15_998_000,
    )

    received = inventory_events.validate_json(sent.model_dump_json())

    assert isinstance(received, StockReserved)
    assert received == sent


def test_unknown_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        inventory_commands.validate_python({"type": "DropTable", "order_id": str(uuid4())})
