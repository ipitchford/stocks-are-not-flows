from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from housing_pressure.ident0.diagnostics import (
    GateStatus,
    ParameterBounds,
    central_difference_jacobian,
    classification_summary,
    column_angle_diagnostics,
    coverage_summary,
    false_attribution_summary,
    jacobian_step_sweep,
    load_config,
    objective_profile,
    recover_multistart,
    sign_recovery_summary,
    summarize_profile,
    svd_diagnostics,
)
from housing_pressure.ident0.errors import InvariantViolation


CONFIG_PATH = Path(__file__).parents[2] / "configs" / "ident0.json"


def test_config_loader_freezes_three_scaled_steps() -> None:
    config = load_config(CONFIG_PATH)

    assert config.years == tuple(range(2008, 2020))
    assert config.finite_difference_steps == (0.005, 0.01, 0.02)
    assert dict(config.economic_materiality)["owner_share_pp"] == 1.0

    invalid = replace(config, finite_difference_steps=(0.01,))
    with pytest.raises(InvariantViolation, match="exactly"):
        invalid.validate()


def test_central_jacobian_is_scaled_by_parameter_ranges_and_moment_scales() -> None:
    bounds = ParameterBounds(names=("a", "b"), lower=(0.0, 0.0), upper=(2.0, 4.0))

    def model(theta: np.ndarray) -> np.ndarray:
        return np.asarray((2.0 * theta[0] + 3.0 * theta[1], theta[0] - theta[1]))

    estimate = central_difference_jacobian(
        model,
        (1.0, 2.0),
        bounds,
        step_fraction=0.01,
        moment_scale=(2.0, 1.0),
    )

    np.testing.assert_allclose(estimate.matrix, ((2.0, 6.0), (2.0, -4.0)), atol=1e-11)


def test_jacobian_sweep_svd_and_angles_detect_collinearity() -> None:
    config = load_config(CONFIG_PATH)
    bounds = ParameterBounds(names=("a", "b"), lower=(0.0, 0.0), upper=(1.0, 1.0))

    def identified(theta: np.ndarray) -> np.ndarray:
        return np.asarray((theta[0] + theta[1], theta[0] - theta[1]))

    sweep = jacobian_step_sweep(identified, (0.5, 0.5), bounds, config)
    assert sweep.status is GateStatus.PASS
    assert sweep.rank_invariant
    assert all(item.rank == 2 for item in sweep.svd)

    collinear = np.asarray(((1.0, 2.0), (2.0, 4.0), (3.0, 6.0)))
    svd = svd_diagnostics(
        collinear,
        rank_ratio_min=config.rank_ratio_min,
        condition_number_max=config.condition_number_max,
    )
    angles = column_angle_diagnostics(collinear, names=("a", "b"), maximum_absolute_cosine=0.99)
    assert svd.status is GateStatus.FAIL
    assert svd.rank == 1
    assert angles.status is GateStatus.FAIL
    assert angles.maximum_absolute_cosine == pytest.approx(1.0)


def test_central_jacobian_refuses_boundary_one_sided_substitution() -> None:
    bounds = ParameterBounds(names=("a",), lower=(0.0,), upper=(1.0,))

    with pytest.raises(InvariantViolation, match="exits bounds"):
        central_difference_jacobian(
            lambda theta: theta,
            (0.0,),
            bounds,
            step_fraction=0.01,
        )


def test_multistart_recovery_and_profile_are_generic_over_callables() -> None:
    bounds = ParameterBounds(names=("amplitude",), lower=(0.05,), upper=(2.0,))

    def model(theta: np.ndarray) -> np.ndarray:
        return np.asarray((theta[0] ** 2,))

    starts = np.asarray(((0.2,), (0.8,), (1.7,)))
    recovery = recover_multistart(
        model,
        (1.0,),
        bounds,
        starts,
        stability_min=1.0,
    )
    assert recovery.status is GateStatus.PASS
    assert recovery.best is not None
    assert recovery.best.estimate[0] == pytest.approx(1.0, abs=1e-6)

    profile = objective_profile(
        lambda theta: np.asarray((theta[0],)),
        (1.0,),
        ParameterBounds(names=("amplitude",), lower=(0.0,), upper=(2.0,)),
        np.asarray(((0.25,), (1.0,), (1.75,))),
        parameter_index=0,
        grid=(0.5, 1.0, 1.5),
    )
    summary = summarize_profile(
        profile,
        objective_difference_cutoff=0.1,
        parameter_range=2.0,
        maximum_width_fraction=0.5,
    )
    assert profile.status is GateStatus.PASS
    assert profile.minimum_objective == pytest.approx(0.0)
    assert summary.status is GateStatus.PASS
    assert summary.accepted_points == 1


def test_classification_allows_tied_pairwise_truth_and_excludes_zero_anchor() -> None:
    truth = np.asarray(((1.0, 0.0), (0.0, -1.0), (1.0, -1.0), (0.0, 0.0)))
    estimates = np.asarray(((0.9, 0.1), (0.1, -0.8), (0.8, -0.7), (0.0, 0.0)))

    summary = classification_summary(
        truth,
        estimates,
        block_names=("top", "middle"),
        minimum_accuracy=1.0,
    )

    assert summary.status is GateStatus.PASS
    assert summary.evaluated_cases == 3
    assert summary.correct_cases == 3
    assert summary.per_block_evaluated == (1, 1)


def test_false_attribution_coverage_and_sign_summaries_return_gate_objects() -> None:
    truth = np.asarray(((0.0, 1.0), (0.0, -1.0), (1.0, 0.0)))
    estimates = np.asarray(((0.1, 0.9), (0.2, -0.8), (0.9, 0.1)))
    lower = np.asarray(((-0.2, 0.5), (-0.1, -1.2), (0.6, -0.2)))
    upper = np.asarray(((0.3, 1.3), (0.4, -0.5), (1.2, 0.3)))

    false_attribution = false_attribution_summary(
        truth,
        estimates,
        lower,
        upper,
        focal_index=0,
        false_positive_max=0.05,
        focal_largest_max=0.10,
    )
    assert false_attribution.status is GateStatus.PASS
    assert false_attribution.eligible_cases == 2
    assert false_attribution.false_positive_rate == 0.0

    # Omitted-mechanism DGPs have zero truth for every fitted block.  Explicit
    # eligibility keeps those scientifically essential cases in the audit.
    omitted_truth = np.zeros((2, 2))
    omitted_estimates = np.asarray(((0.8, 0.2), (0.1, 0.9)))
    omitted_lower = np.asarray(((0.2, -0.2), (-0.2, 0.4)))
    omitted_upper = np.asarray(((1.0, 0.5), (0.4, 1.2)))
    omitted = false_attribution_summary(
        omitted_truth,
        omitted_estimates,
        omitted_lower,
        omitted_upper,
        focal_index=0,
        false_positive_max=0.05,
        focal_largest_max=0.10,
        eligible_mask=np.asarray((True, True)),
    )
    assert omitted.eligible_cases == 2
    assert omitted.false_positive_rate == pytest.approx(0.5)
    assert omitted.focal_largest_rate == pytest.approx(0.5)
    assert omitted.status is GateStatus.FAIL

    repeated_truth = np.zeros((10, 1))
    interval_lower = np.full((10, 1), -1.0)
    interval_upper = np.full((10, 1), 1.0)
    interval_lower[-1, 0] = 0.1
    coverage = coverage_summary(
        repeated_truth,
        interval_lower,
        interval_upper,
        minimum=0.90,
        maximum=0.98,
        parameter_names=("top",),
    )
    assert coverage.status is GateStatus.PASS
    assert coverage.overall_coverage == pytest.approx(0.9)

    signs = sign_recovery_summary(
        truth,
        estimates,
        focal_index=0,
        minimum_true_magnitude=0.5,
        minimum_accuracy=0.95,
    )
    assert signs.status is GateStatus.PASS
    assert signs.eligible_cases == 1
