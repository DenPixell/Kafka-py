import pytest

from antifraud.domain.rules import (
    CheckContext,
    FrequentOrders,
    LargeAmount,
    NewCountry,
    Rule,
    evaluate,
)

RUB = 100
RULES: list[Rule] = [
    LargeAmount(threshold_kopecks=400_000 * RUB, score=50),
    FrequentOrders(max_orders=3, score=70),
    NewCountry(threshold_kopecks=150_000 * RUB, score=40),
]
THRESHOLD = 70


def context(
    total_rub: int = 80_000,
    country: str = "RU",
    recent_orders: int = 0,
    known: frozenset[str] = frozenset({"RU"}),
) -> CheckContext:
    return CheckContext(
        total_kopecks=total_rub * RUB,
        delivery_country=country,
        recent_orders=recent_orders,
        known_countries=known,
    )


def test_ordinary_order_passes_with_zero_score() -> None:
    verdict = evaluate(context(), RULES, THRESHOLD)

    assert (verdict.approved, verdict.score, verdict.reasons) == (True, 0, ())


def test_large_amount_alone_is_not_enough_to_reject() -> None:
    verdict = evaluate(context(total_rub=589_990), RULES, THRESHOLD)

    assert verdict.approved is True
    assert verdict.reasons == ("large_amount",)


def test_large_amount_to_new_country_is_rejected() -> None:
    verdict = evaluate(context(total_rub=589_990, country="AM"), RULES, THRESHOLD)

    assert verdict.approved is False
    assert verdict.score == 90
    assert verdict.reasons == ("large_amount", "new_country")


@pytest.mark.parametrize(("recent", "approved"), [(2, True), (3, False)])
def test_fourth_order_in_window_is_rejected(recent: int, approved: bool) -> None:
    verdict = evaluate(context(recent_orders=recent), RULES, THRESHOLD)

    assert verdict.approved is approved


def test_new_customer_has_no_new_country() -> None:
    verdict = evaluate(
        context(total_rub=200_000, country="AM", known=frozenset()), RULES, THRESHOLD
    )

    assert verdict.reasons == ()


def test_cheap_order_to_new_country_is_fine() -> None:
    verdict = evaluate(context(total_rub=40_000, country="AM"), RULES, THRESHOLD)

    assert verdict.reasons == ()
