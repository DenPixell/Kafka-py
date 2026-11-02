from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from contracts import Message


def test_each_message_gets_its_own_id() -> None:
    order_id = uuid4()

    first = Message(type="Test", order_id=order_id)
    second = Message(type="Test", order_id=order_id)

    assert first.message_id != second.message_id


def test_occurred_at_defaults_to_utc() -> None:
    message = Message(type="Test", order_id=uuid4())

    assert message.occurred_at.tzinfo is UTC


def test_naive_datetime_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Message(type="Test", order_id=uuid4(), occurred_at=datetime(2026, 11, 2, 12, 0))  # noqa: DTZ001


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Message.model_validate({"type": "Test", "order_id": str(uuid4()), "amount": 100})


def test_json_round_trip_keeps_all_fields() -> None:
    message = Message(type="Test", order_id=uuid4())

    restored = Message.model_validate_json(message.model_dump_json())

    assert restored == message


def test_partition_key_is_order_id() -> None:
    order_id = uuid4()

    message = Message(type="Test", order_id=order_id)

    assert message.partition_key() == str(order_id).encode()
