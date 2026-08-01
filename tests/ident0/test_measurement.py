from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys

import pytest

from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.incidence import (
    ClosureClass,
    UnitConvention,
    build_incidence_ledger,
)
from housing_pressure.ident0.measurement import (
    RankWeight,
    WealthObservationMap,
    WealthPriceBasis,
    evolve_non_housing_wealth,
    observe_non_housing_wealth,
    validate_incidence_wealth_bridge,
)


def _flow(
    group: str,
    *,
    opening: float,
    resource: float,
    valuation: float = 0.0,
):
    return evolve_non_housing_wealth(
        model_group=group,
        year=2008,
        opening_non_housing_wealth=opening,
        latent_resource_flow=resource,
        resource_pass_through=0.5,
        other_active_accumulation=2.0,
        withdrawals=1.0,
        debt_change=3.0,
        realised_returns=4.0,
        non_housing_valuation_change=valuation,
        entry_exit=-2.0,
    )


def _mapping(basis: WealthPriceBasis) -> WealthObservationMap:
    return WealthObservationMap(
        mapping_id=f"gb-was-{basis.value.lower()}",
        geography="Great Britain",
        top_rank="observed_top_decile",
        price_basis=basis,
        rank_weights=(
            RankWeight("high_saver_type", "observed_top_decile", 0.8, 0.7),
            RankWeight("high_saver_type", "observed_other_90", 0.2, 0.3),
            RankWeight("other_type", "observed_top_decile", 0.1, 0.2),
            RankWeight("other_type", "observed_other_90", 0.9, 0.8),
        ),
    )


def test_stock_flow_bridge_separates_active_passive_and_debt_components() -> None:
    flow = _flow("top", opening=100.0, resource=10.0, valuation=6.0)

    assert flow.active_accumulation_from_resource == pytest.approx(5.0)
    assert flow.closing_constant_price_wealth == pytest.approx(105.0)
    assert flow.closing_current_price_wealth == pytest.approx(111.0)
    assert flow.constant_price_residual == pytest.approx(0.0)
    assert flow.current_price_residual == pytest.approx(0.0)


def test_property_revaluation_cannot_define_non_housing_resource_flow() -> None:
    with pytest.raises(InvariantViolation, match="property revaluation is forbidden"):
        evolve_non_housing_wealth(
            model_group="top",
            year=2008,
            opening_non_housing_wealth=100.0,
            latent_resource_flow=10.0,
            resource_pass_through=0.5,
            other_active_accumulation=0.0,
            withdrawals=0.0,
            debt_change=0.0,
            realised_returns=0.0,
            non_housing_valuation_change=0.0,
            entry_exit=0.0,
            property_revaluation=20.0,
        )


def test_closing_stock_mutation_is_rejected() -> None:
    flow = _flow("top", opening=100.0, resource=10.0, valuation=6.0)

    with pytest.raises(InvariantViolation, match="current-price stock-flow identity"):
        replace(flow, closing_current_price_wealth=flow.closing_current_price_wealth + 1.0)


def test_incidence_to_wealth_bridge_uses_aggregate_units_and_date() -> None:
    ledger = build_incidence_ledger(
        experiment_id="e0-bridge",
        year=2008,
        closure_class=ClosureClass.E0_REDISTRIBUTION,
        top_amount=10.0,
        top_unit=UnitConvention.PER_RECIPIENT,
        top_recipient_mass=0.1,
        middle_amount=-1.0,
        middle_unit=UnitConvention.AGGREGATE,
        middle_recipient_mass=0.6,
        aggregate_resources_delta=0.0,
    )
    top = _flow("top", opening=100.0, resource=1.0)
    middle = _flow("middle", opening=80.0, resource=-1.0)

    validate_incidence_wealth_bridge(ledger, [top, middle])

    wrong_unit_value = _flow("top", opening=100.0, resource=10.0)
    with pytest.raises(InvariantViolation, match="aggregate top incidence"):
        validate_incidence_wealth_bridge(ledger, [wrong_unit_value, middle])


def test_observation_map_distinguishes_types_from_round_specific_ranks() -> None:
    high = _flow("high_saver_type", opening=120.0, resource=10.0, valuation=12.0)
    other = _flow("other_type", opening=80.0, resource=-4.0, valuation=2.0)
    observation = observe_non_housing_wealth(
        [high, other], _mapping(WealthPriceBasis.CURRENT_PRICE)
    )

    opening = dict(observation.opening_rank_stocks)
    closing = dict(observation.closing_rank_stocks)
    assert opening["observed_top_decile"] == pytest.approx(104.0)
    assert closing["observed_top_decile"] != pytest.approx(opening["observed_top_decile"])
    assert observation.decomposition_residual == pytest.approx(0.0, abs=1e-12)
    assert observation.top_share_change == pytest.approx(
        observation.stock_flow_numerator_effect
        + observation.rank_reclassification_effect
        + observation.denominator_effect
    )


def test_current_and_constant_price_observations_are_distinct() -> None:
    high = _flow("high_saver_type", opening=120.0, resource=10.0, valuation=12.0)
    other = _flow("other_type", opening=80.0, resource=-4.0, valuation=2.0)
    current = observe_non_housing_wealth([high, other], _mapping(WealthPriceBasis.CURRENT_PRICE))
    constant = observe_non_housing_wealth([high, other], _mapping(WealthPriceBasis.CONSTANT_PRICE))

    assert current.closing_denominator != pytest.approx(constant.closing_denominator)
    assert current.closing_top_share != pytest.approx(constant.closing_top_share)


def test_rank_map_requires_exhaustive_weights_and_distinct_namespaces() -> None:
    with pytest.raises(InvariantViolation, match="do not sum to one"):
        WealthObservationMap(
            mapping_id="bad-weights",
            geography="Great Britain",
            top_rank="observed_top_decile",
            price_basis=WealthPriceBasis.CURRENT_PRICE,
            rank_weights=(
                RankWeight("type_a", "observed_top_decile", 0.7, 0.7),
                RankWeight("type_a", "observed_other_90", 0.2, 0.3),
            ),
        )

    with pytest.raises(InvariantViolation, match="distinct labels"):
        WealthObservationMap(
            mapping_id="silent-identity",
            geography="Great Britain",
            top_rank="top",
            price_basis=WealthPriceBasis.CURRENT_PRICE,
            rank_weights=(
                RankWeight("top", "top", 1.0, 1.0),
                RankWeight("other", "other", 1.0, 1.0),
            ),
        )


def test_observed_share_mutation_is_rejected() -> None:
    high = _flow("high_saver_type", opening=120.0, resource=10.0, valuation=12.0)
    other = _flow("other_type", opening=80.0, resource=-4.0, valuation=2.0)
    observation = observe_non_housing_wealth(
        [high, other], _mapping(WealthPriceBasis.CURRENT_PRICE)
    )

    with pytest.raises(InvariantViolation, match="denominator is inconsistent"):
        replace(observation, closing_denominator=observation.closing_denominator + 1.0)


def test_rank_stock_mutation_cannot_hide_outside_the_top_rank() -> None:
    high = _flow("high_saver_type", opening=120.0, resource=10.0, valuation=12.0)
    other = _flow("other_type", opening=80.0, resource=-4.0, valuation=2.0)
    observation = observe_non_housing_wealth(
        [high, other], _mapping(WealthPriceBasis.CURRENT_PRICE)
    )
    mutated = tuple(
        (rank, value + 1.0 if rank == "observed_other_90" else value)
        for rank, value in observation.closing_stocks_at_opening_ranks
    )

    with pytest.raises(InvariantViolation, match="preserve the denominator"):
        replace(observation, closing_stocks_at_opening_ranks=mutated)


def test_measurement_failures_remain_active_under_optimized_python() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(source_root), environment.get("PYTHONPATH", "")]
    )
    script = """
from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.measurement import evolve_non_housing_wealth
try:
    evolve_non_housing_wealth(
        model_group='top', year=2008, opening_non_housing_wealth=100.0,
        latent_resource_flow=1.0, resource_pass_through=0.5,
        other_active_accumulation=0.0, withdrawals=0.0, debt_change=0.0,
        realised_returns=0.0, non_housing_valuation_change=0.0,
        entry_exit=0.0, property_revaluation=1.0,
    )
except InvariantViolation:
    raise SystemExit(0)
raise SystemExit(9)
"""
    result = subprocess.run(
        [sys.executable, "-O", "-c", script],
        check=False,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
