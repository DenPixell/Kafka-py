from uuid import uuid4

import pytest
from pydantic import ValidationError

from contracts import CheckOrder, FraudCheckFailed, antifraud_events


def test_failed_check_is_parsed_with_reasons() -> None:
    sent = FraudCheckFailed(order_id=uuid4(), score=90, reasons=("large_amount", "new_country"))

    received = antifraud_events.validate_json(sent.model_dump_json())

    assert received == sent


def test_failed_check_must_explain_itself() -> None:
    with pytest.raises(ValidationError):
        FraudCheckFailed(order_id=uuid4(), score=90, reasons=())


def test_country_must_be_iso_code() -> None:
    with pytest.raises(ValidationError):
        CheckOrder(order_id=uuid4(), user_id="anna", total_kopecks=100, delivery_country="Russia")
