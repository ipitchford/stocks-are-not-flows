"""Tests for the hand-verifiable IDENT-0 local-response design."""

from __future__ import annotations

import numpy as np
import pytest

from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.response_model import (
    ABSENT_PUBLIC_CORE_MEASUREMENTS,
    BLOCK_NAMES,
    DIAGNOSTIC_ROLE,
    MODELLED_PUBLIC_CORE_OBSERVATIONS,
    MOMENT_NAMES,
    NONMODELLED_PUBLIC_CORE_HOLDOUTS,
    PENDING_PUBLIC_CORE_TARGETS,
    PUBLIC_CORE_OBSERVATIONS,
    TARGET_ROLE,
    UNAVAILABLE_RESPONSE_MEASUREMENTS,
    YEARS,
    LocalResponseModel,
    common_ramp,
)


def _amplitudes(**updates: float) -> dict[str, float]:
    values = {name: 0.0 for name in BLOCK_NAMES}
    values.update(updates)
    return values


def test_common_ramp_is_shared_and_normalised() -> None:
    ramp = common_ramp()

    assert ramp.shape == (12,)
    assert ramp[0] == pytest.approx(0.0)
    assert ramp[-1] == pytest.approx(1.0)
    assert np.allclose(np.diff(ramp), np.repeat(1.0 / 11.0, 11))

    model = LocalResponseModel.baseline()
    paths = model.shock_paths(_amplitudes(z_top=0.8, z_middle=-0.4, credit=0.2))
    for block, amplitude in (("z_top", 0.8), ("z_middle", -0.4), ("credit", 0.2)):
        column = paths[:, BLOCK_NAMES.index(block)]
        assert np.allclose(column, amplitude * ramp)


@pytest.mark.parametrize("years", [(2008,), (2008, 2008), (2009, 2008)])
def test_common_ramp_rejects_invalid_year_axes(years: tuple[int, ...]) -> None:
    with pytest.raises(InvariantViolation):
        common_ramp(years)


def test_public_core_schedule_preserves_roles_geographies_and_field_periods() -> None:
    model = LocalResponseModel.baseline()
    target = model.observation_schedule(TARGET_ROLE)
    diagnostics = model.observation_schedule(DIAGNOSTIC_ROLE)

    assert len(target) == 57
    assert len(diagnostics) == 30
    assert len(MODELLED_PUBLIC_CORE_OBSERVATIONS) == 87
    assert PUBLIC_CORE_OBSERVATIONS is MODELLED_PUBLIC_CORE_OBSERVATIONS
    assert len({item.observation_id for item in MODELLED_PUBLIC_CORE_OBSERVATIONS}) == 87
    assert {item.geography for item in target} == {"England", "Great Britain", "United Kingdom"}
    assert any(item.period == "Wave 2 (2008-10)" for item in target)
    assert any(item.period == "2018-19" for item in target)
    assert all(item.role == TARGET_ROLE for item in target)
    assert all(item.role == DIAGNOSTIC_ROLE for item in diagnostics)

    h01 = [item for item in diagnostics if item.observation_id.startswith("H01_")]
    assert len(h01) == 18
    assert {item.anchor_year for item in h01} == set(range(2009, 2018))
    assert {item.moment for item in h01} == {
        "owner_share_25_44_pp",
        "private_renter_share_25_44_pp",
    }
    assert {item.period for item in h01} == {
        f"{year}-{str(year + 1)[-2:]}" for year in range(2009, 2018)
    }

    observed_moments = {item.moment for item in MODELLED_PUBLIC_CORE_OBSERVATIONS}
    assert observed_moments.isdisjoint(UNAVAILABLE_RESPONSE_MEASUREMENTS)


def test_predict_is_a_deviation_model_with_expected_top_and_middle_signs() -> None:
    model = LocalResponseModel.baseline()
    zero = model.predict(_amplitudes())
    top = model.predict(_amplitudes(z_top=1.0))
    middle_loss = model.predict(_amplitudes(z_middle=-1.0))

    assert np.all(zero.values == 0.0)
    assert top.value("owner_share_25_44_pp", 2019) < 0.0
    assert top.value("private_renter_share_25_44_pp", 2019) > 0.0
    assert top.value("log_hpi_pct", 2019) > 0.0
    assert middle_loss.value("owner_share_25_44_pp", 2019) < 0.0
    assert middle_loss.value("private_renter_share_25_44_pp", 2019) > 0.0

    # Every baseline-year response is exactly a modelled zero deviation.
    assert np.all(top.values[YEARS.index(2008), :] == 0.0)


def test_analytic_jacobian_matches_central_differences_and_is_full_rank() -> None:
    model = LocalResponseModel.baseline()
    truth = np.asarray([0.35, -0.20, 0.10, -0.15, 0.05, 0.12, -0.08])

    analytic = model.analytic_jacobian(TARGET_ROLE)
    numerical = model.finite_difference_jacobian(truth, step=0.005, role=TARGET_ROLE)

    assert analytic.shape == (57, 7)
    assert np.allclose(analytic, numerical, rtol=1e-11, atol=1e-11)
    assert np.linalg.matrix_rank(analytic) == len(BLOCK_NAMES)


def test_top_wealth_rows_use_the_executable_accumulated_stock_tangent() -> None:
    model = LocalResponseModel.baseline()
    model.verify_measurement_bridge()
    top = model.predict(_amplitudes(z_top=1.0))

    assert top.value("nhw_top10_share_pp", 2019) == pytest.approx(1.70)
    # The 2009 flow has only begun to accumulate, so this is deliberately not
    # one-eleventh of the terminal stock-share effect.
    assert top.value("nhw_top10_share_pp", 2009) == pytest.approx(1.70 / 66.0)
    assert top.value("nhw_top10_share_pp", 2009) != pytest.approx(1.70 / 11.0)


def test_known_negative_exact_and_near_collinearity_are_visible() -> None:
    exact = LocalResponseModel.known_negative_collinear()
    near = LocalResponseModel.known_negative_collinear(near=True, gap=1e-7)

    exact_jacobian = exact.analytic_jacobian()
    near_jacobian = near.analytic_jacobian()
    exact_top = exact_jacobian[:, BLOCK_NAMES.index("z_top")]
    exact_middle = exact_jacobian[:, BLOCK_NAMES.index("z_middle")]

    assert np.array_equal(exact_top, exact_middle)
    assert np.linalg.matrix_rank(exact_jacobian) < len(BLOCK_NAMES)
    assert np.linalg.matrix_rank(near_jacobian) == len(BLOCK_NAMES)
    assert np.linalg.cond(near_jacobian) > 1e6
    with pytest.raises(InvariantViolation, match="disables the wealth bridge"):
        exact.verify_measurement_bridge()


def test_amplitudes_are_complete_finite_and_alias_safe() -> None:
    model = LocalResponseModel.baseline()

    alias_values = _amplitudes()
    alias_values.pop("z_top")
    alias_values["top_resources"] = 0.25
    vector = model.amplitude_vector(alias_values)
    assert vector[BLOCK_NAMES.index("z_top")] == pytest.approx(0.25)

    with pytest.raises(InvariantViolation, match="missing"):
        model.amplitude_vector({"z_top": 1.0})
    with pytest.raises(InvariantViolation, match="unknown shock block"):
        model.amplitude_vector({**_amplitudes(), "mystery": 1.0})
    with pytest.raises(InvariantViolation, match="more than once"):
        model.amplitude_vector({**_amplitudes(), "top_resources": 1.0})
    with pytest.raises(InvariantViolation, match="finite"):
        model.amplitude_vector([0.0, 0.0, np.nan, 0.0, 0.0, 0.0, 0.0])


def test_absent_and_nonmodelled_measurements_are_never_numeric_zero() -> None:
    model = LocalResponseModel.baseline()
    panel = model.predict(_amplitudes())

    for moment in UNAVAILABLE_RESPONSE_MEASUREMENTS:
        assert moment not in MOMENT_NAMES
        assert panel.optional_value(moment, 2019) is None
        assert model.public_core_value(panel, moment, 2019) is None
        with pytest.raises(InvariantViolation, match="absent public core|nonmodelled holdout"):
            panel.value(moment, 2019)

    assert len(ABSENT_PUBLIC_CORE_MEASUREMENTS) == 4
    assert not PENDING_PUBLIC_CORE_TARGETS
    assert {item.preregistered_id for item in NONMODELLED_PUBLIC_CORE_HOLDOUTS.values()} == {
        "H02_TENURE_ALLAGE",
        "H03_RENT_BURDEN",
        "H04_PROPERTY_WEALTH",
        "H05_PRICE_RENT_INDEX",
        "H07_MLAR_BTL",
        "H08_FTB_PROFILE",
        "H09_EPLS_2018",
        "H10_HMRC_TX",
        "H11_HPI_BUYER_CUTS",
        "H12_POST2019",
    }
    assert all(
        item.status == "nonmodelled_holdout" for item in NONMODELLED_PUBLIC_CORE_HOLDOUTS.values()
    )


def test_coefficient_property_is_defensive_and_invalid_requests_fail_closed() -> None:
    model = LocalResponseModel.baseline()
    external = model.coefficients
    external[0, 0] = 999.0

    assert model.coefficient("owner_share_25_44_pp", "z_top") == pytest.approx(-1.45)
    with pytest.raises(InvariantViolation, match="unknown response moment"):
        model.coefficient("gross_owner_to_landlord_flow", "z_top")
    with pytest.raises(InvariantViolation, match="unknown observation role"):
        model.observation_schedule("secret_fit_target")
    with pytest.raises(InvariantViolation, match="finite and positive"):
        model.finite_difference_jacobian(step=0.0)
