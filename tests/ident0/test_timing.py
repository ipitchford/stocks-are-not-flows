import math
from dataclasses import replace

import pytest

from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.timing import (
    compare_advance_and_arrears,
    solve_log_renter,
    verify_tim1,
)


def test_tim1_exact_ratio_and_value_shift() -> None:
    comparison = compare_advance_and_arrears(
        resources=2.4,
        rent=0.6,
        gross_return=1.08,
        alpha=0.25,
        beta=0.7,
    )
    verify_tim1(comparison)
    assert comparison.service_ratio == pytest.approx(1.08)
    assert comparison.utility_difference == pytest.approx(0.25 * math.log(1.08))


def test_fixed_resource_non_rent_choices_do_not_move() -> None:
    comparison = compare_advance_and_arrears(2.4, 0.6, 1.08, 0.25, 0.7)
    assert comparison.arrears.consumption_now == comparison.advance.consumption_now
    assert comparison.arrears.financial_saving == comparison.advance.financial_saving
    assert comparison.arrears.consumption_later == comparison.advance.consumption_later


def test_advance_rent_mutation_is_detected() -> None:
    comparison = compare_advance_and_arrears(2.4, 0.6, 1.08, 0.25, 0.7)
    mutated = replace(
        comparison,
        arrears=comparison.advance,
        service_ratio=1.0,
        utility_difference=0.0,
    )
    with pytest.raises(InvariantViolation, match="TIM-1 failed"):
        verify_tim1(mutated)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"resources": 0.0},
        {"rent": -1.0},
        {"gross_return": float("nan")},
        {"alpha": 0.0},
        {"beta": -0.2},
    ],
)
def test_invalid_domain_is_failure_closed(kwargs: dict[str, float]) -> None:
    inputs = dict(resources=2.4, rent=0.6, gross_return=1.08, alpha=0.25, beta=0.7)
    inputs.update(kwargs)
    with pytest.raises(InvariantViolation, match="positive finite"):
        solve_log_renter(**inputs, arrears=True)
