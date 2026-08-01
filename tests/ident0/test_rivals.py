"""Tests for rival-only and known-negative IDENT-0 DGPs."""

from __future__ import annotations

import numpy as np
import pytest

from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.response_model import (
    BLOCK_NAMES,
    MOMENT_NAMES,
    UNAVAILABLE_RESPONSE_MEASUREMENTS,
    LocalResponseModel,
)
from housing_pressure.ident0.rivals import (
    EXACT_TOP_MIMIC,
    INSTITUTIONAL_ENTRY,
    PLANNING_RESTRICTION,
    RENTAL_SEGMENTATION,
    RIVAL_CATALOGUE,
    RIVAL_NAMES,
    SOCIAL_COMPARISON,
    exact_top_mimic,
    get_rival,
    project_rival_onto_model,
    simulate_all_rivals,
    simulate_rival,
)


def test_catalogue_contains_required_adversarial_rivals_in_stable_order() -> None:
    assert RIVAL_NAMES == (
        SOCIAL_COMPARISON,
        INSTITUTIONAL_ENTRY,
        RENTAL_SEGMENTATION,
        PLANNING_RESTRICTION,
    )
    assert tuple(RIVAL_CATALOGUE) == RIVAL_NAMES
    assert all(RIVAL_CATALOGUE[name].name == name for name in RIVAL_NAMES)


@pytest.mark.parametrize(
    "name",
    [SOCIAL_COMPARISON, INSTITUTIONAL_ENTRY, RENTAL_SEGMENTATION, PLANNING_RESTRICTION],
)
def test_rival_dgps_have_zero_fitted_block_truth_and_use_common_ramp(name: str) -> None:
    model = LocalResponseModel.baseline()
    simulation = simulate_rival(model, name, amplitude=0.75)
    rival = RIVAL_CATALOGUE[name]
    terminal = rival.terminal_loadings(model) * 0.75
    reference = model.zero_amplitudes()
    reference[rival.reference_block] = rival.reference_weight * 0.75
    expected = (
        model.predict(reference).values + model.ramp[:, None] * (0.75 * rival.residual)[None, :]
    )
    for moment in rival.zero_response_moments:
        expected[:, MOMENT_NAMES.index(moment)] = 0.0

    assert simulation.true_top_amplitude == 0.0
    assert simulation.base_truth == tuple(0.0 for _ in BLOCK_NAMES)
    assert np.all(simulation.panel.values[0, :] == 0.0)
    assert np.allclose(simulation.panel.values[-1, :], terminal)
    assert np.allclose(simulation.panel.values, expected)


@pytest.mark.parametrize(
    "name",
    [SOCIAL_COMPARISON, INSTITUTIONAL_ENTRY, RENTAL_SEGMENTATION],
)
def test_housing_near_mimics_do_not_manufacture_top_wealth_response(name: str) -> None:
    model = LocalResponseModel.baseline()
    simulation = simulate_rival(model, name)

    assert simulation.panel.value("nhw_top10_share_pp", 2019) == pytest.approx(0.0, abs=1e-14)
    assert simulation.panel.value("log_hpi_pct", 2019) > 0.0
    assert simulation.true_top_amplitude == 0.0


def test_planning_restriction_acts_through_primitive_supply_capacity() -> None:
    model = LocalResponseModel.baseline()
    simulation = simulate_rival(model, PLANNING_RESTRICTION)

    assert simulation.panel.value("net_additions_rate_pp", 2019) < 0.0
    assert simulation.panel.value("log_hpi_pct", 2019) > 0.0
    assert simulation.panel.value("owner_share_25_44_pp", 2019) < 0.0


def test_exact_top_mimic_is_an_impossible_identification_known_negative() -> None:
    model = LocalResponseModel.baseline()
    dgp = exact_top_mimic(model)
    simulation = dgp.simulate(model, amplitude=0.65)
    projection = project_rival_onto_model(model, simulation)

    assert dgp.name == EXACT_TOP_MIMIC
    assert dgp.known_negative is True
    assert simulation.known_negative is True
    assert simulation.true_top_amplitude == 0.0
    assert projection.rank == len(BLOCK_NAMES)
    assert projection.amplitude("z_top") == pytest.approx(0.65, abs=1e-11)
    assert projection.residual_rmse == pytest.approx(0.0, abs=1e-11)
    for block in BLOCK_NAMES[1:]:
        assert projection.amplitude(block) == pytest.approx(0.0, abs=1e-11)


def test_registered_rivals_are_difficult_but_not_exactly_identical_to_top() -> None:
    model = LocalResponseModel.baseline()
    for simulation in simulate_all_rivals(model):
        projection = project_rival_onto_model(model, simulation)
        assert projection.rank == len(BLOCK_NAMES)
        assert np.isfinite(projection.residual_rmse)
        assert projection.residual_rmse > 1e-8


def test_absent_and_nonmodelled_objects_remain_unavailable_under_every_rival() -> None:
    model = LocalResponseModel.baseline()
    for simulation in simulate_all_rivals(model):
        assert set(simulation.panel.moments) == set(MOMENT_NAMES)
        for moment in UNAVAILABLE_RESPONSE_MEASUREMENTS:
            assert simulation.public_core_value(model, moment, 2019) is None


def test_rival_noise_is_seeded_and_does_not_change_declared_truth() -> None:
    model = LocalResponseModel.baseline()
    first = simulate_rival(model, SOCIAL_COMPARISON, noise_std=0.1, seed=20260801)
    second = simulate_rival(model, SOCIAL_COMPARISON, noise_std=0.1, seed=20260801)
    different = simulate_rival(model, SOCIAL_COMPARISON, noise_std=0.1, seed=20260802)

    assert np.array_equal(first.panel.values, second.panel.values)
    assert not np.array_equal(first.panel.values, different.panel.values)
    assert first.base_truth == tuple(0.0 for _ in BLOCK_NAMES)


def test_invalid_rival_requests_fail_with_explicit_errors() -> None:
    model = LocalResponseModel.baseline()

    with pytest.raises(InvariantViolation, match="unknown rival DGP"):
        get_rival("wealth_fairy")
    with pytest.raises(InvariantViolation, match="non-negative"):
        simulate_rival(model, SOCIAL_COMPARISON, noise_std=-0.1)
    with pytest.raises(InvariantViolation, match="finite"):
        simulate_rival(model, SOCIAL_COMPARISON, amplitude=np.nan)
    with pytest.raises(InvariantViolation, match="LocalResponseModel"):
        exact_top_mimic(object())  # type: ignore[arg-type]
