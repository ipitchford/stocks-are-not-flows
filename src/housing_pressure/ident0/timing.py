"""Scoped R06 renter-timing identities.

This module proves only the interior logarithmic allocation identity used by
TIM-1. It does not claim that equilibrium prices are unchanged by retiming.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from .errors import InvariantViolation


@dataclass(frozen=True)
class RenterAllocation:
    consumption_now: float
    rental_services: float
    financial_saving: float
    consumption_later: float
    indirect_utility: float
    present_rent_price: float


@dataclass(frozen=True)
class TimingComparison:
    advance: RenterAllocation
    arrears: RenterAllocation
    service_ratio: float
    utility_difference: float
    expected_service_ratio: float
    expected_utility_difference: float


def solve_log_renter(
    resources: float,
    rent: float,
    gross_return: float,
    alpha: float,
    beta: float,
    *,
    arrears: bool,
) -> RenterAllocation:
    """Solve the interior log renter allocation at fixed prices and resources."""

    values = {
        "resources": resources,
        "rent": rent,
        "gross_return": gross_return,
        "alpha": alpha,
        "beta": beta,
    }
    bad = [name for name, value in values.items() if not math.isfinite(value) or value <= 0]
    if bad:
        raise InvariantViolation(f"TIM-1 requires positive finite inputs: {bad}")

    present_rent = rent / gross_return if arrears else rent
    weight = 1.0 + alpha + beta
    consumption_now = resources / weight
    rental_services = alpha * resources / (weight * present_rent)
    financial_saving = beta * resources / weight
    consumption_later = gross_return * financial_saving
    if min(consumption_now, rental_services, financial_saving, consumption_later) <= 0:
        raise InvariantViolation("TIM-1 interior allocation reached a non-positive choice")

    utility = (
        math.log(consumption_now)
        + alpha * math.log(rental_services)
        + beta * math.log(consumption_later)
    )
    return RenterAllocation(
        consumption_now=consumption_now,
        rental_services=rental_services,
        financial_saving=financial_saving,
        consumption_later=consumption_later,
        indirect_utility=utility,
        present_rent_price=present_rent,
    )


def compare_advance_and_arrears(
    resources: float,
    rent: float,
    gross_return: float,
    alpha: float,
    beta: float,
) -> TimingComparison:
    """Return the scoped TIM-1 demand and value comparison."""

    advance = solve_log_renter(resources, rent, gross_return, alpha, beta, arrears=False)
    arrears = solve_log_renter(resources, rent, gross_return, alpha, beta, arrears=True)
    return TimingComparison(
        advance=advance,
        arrears=arrears,
        service_ratio=arrears.rental_services / advance.rental_services,
        utility_difference=arrears.indirect_utility - advance.indirect_utility,
        expected_service_ratio=gross_return,
        expected_utility_difference=alpha * math.log(gross_return),
    )


def verify_tim1(comparison: TimingComparison, *, tolerance: float = 1e-12) -> None:
    """Raise unless both exact TIM-1 implications hold within tolerance."""

    if not math.isfinite(tolerance) or tolerance <= 0:
        raise InvariantViolation("TIM-1 tolerance must be positive and finite")
    service_error = abs(comparison.service_ratio - comparison.expected_service_ratio)
    value_error = abs(comparison.utility_difference - comparison.expected_utility_difference)
    if service_error > tolerance or value_error > tolerance:
        raise InvariantViolation(
            f"TIM-1 failed: service_error={service_error:.3e}, value_error={value_error:.3e}"
        )
