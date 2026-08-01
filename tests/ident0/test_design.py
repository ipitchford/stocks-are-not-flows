import numpy as np
import pytest

from housing_pressure.ident0.design import (
    DEFAULT_SHOCK_BLOCKS,
    build_full_preregistered_plan,
    build_smoke_plan,
    denormalize_truth_cases,
    deterministic_starts,
    maximin_latin_hypercube,
    validate_neutral_maps_to_zero,
)
from housing_pressure.ident0.diagnostics import ParameterBounds
from housing_pressure.ident0.errors import InvariantViolation


def test_latin_hypercube_is_deterministic_bounded_and_stratified() -> None:
    first = maximin_latin_hypercube(8, 3, seed=42, lower=0.1, upper=0.9, candidates=4)
    second = maximin_latin_hypercube(8, 3, seed=42, lower=0.1, upper=0.9, candidates=4)

    np.testing.assert_array_equal(first, second)
    assert np.all(first >= 0.1)
    assert np.all(first <= 0.9)
    unit = (first - 0.1) / 0.8
    strata = np.floor(unit * 8).astype(int)
    for column in range(strata.shape[1]):
        assert sorted(strata[:, column].tolist()) == list(range(8))


def test_full_plan_exposes_frozen_workload_without_running_fits() -> None:
    plan = build_full_preregistered_plan(seed=20260801)

    assert plan.block_names == DEFAULT_SHOCK_BLOCKS
    assert plan.truth_cases == 313
    assert plan.noise_free_fits == 313
    assert plan.noisy_fits == 6260
    assert plan.total_fits == 6573
    assert plan.total_optimizer_starts == 210336
    assert plan.kind_counts() == {
        "latin_hypercube": 256,
        "zero_anchor": 1,
        "one_at_a_time_anchor": 14,
        "pairwise_confounding_anchor": 42,
    }
    assert len({case.case_id for case in plan.cases}) == 313


def test_smoke_plan_is_small_and_preserves_anchor_structure() -> None:
    plan = build_smoke_plan(("top", "middle"), lhs_points=2, noisy_replications_per_case=1)

    # 2 LHS + 1 zero + 4 one-at-a-time + 2 opposite-sign pair anchors.
    assert plan.truth_cases == 9
    assert plan.total_fits == 18
    assert plan.total_optimizer_starts == 54


def test_deterministic_starts_and_truth_denormalization_respect_bounds() -> None:
    bounds = ParameterBounds(
        names=("top", "middle"),
        lower=(-2.0, 10.0),
        upper=(2.0, 20.0),
    )
    starts = deterministic_starts(bounds, 5, seed=7, maximin_candidates=4)
    repeated = deterministic_starts(bounds, 5, seed=7, maximin_candidates=4)

    np.testing.assert_array_equal(starts, repeated)
    np.testing.assert_allclose(starts[0], (0.0, 15.0))
    assert np.all(starts >= bounds.lower_array)
    assert np.all(starts <= bounds.upper_array)

    plan = build_smoke_plan(("top", "middle"), lhs_points=1)
    physical = denormalize_truth_cases(plan.cases, bounds)
    assert physical.shape == (8, 2)
    zero_index = [case.case_id for case in plan.cases].index("anchor_zero")
    np.testing.assert_allclose(physical[zero_index], (0.0, 15.0))


def test_full_plan_rejects_dimension_drift() -> None:
    with pytest.raises(InvariantViolation, match="exactly seven"):
        build_full_preregistered_plan(("top", "middle"))


def test_neutral_coordinate_must_map_to_physical_zero() -> None:
    validate_neutral_maps_to_zero(ParameterBounds(names=("top",), lower=(-1.0,), upper=(1.0,)))
    with pytest.raises(InvariantViolation, match="does not map"):
        validate_neutral_maps_to_zero(ParameterBounds(names=("top",), lower=(0.0,), upper=(2.0,)))
