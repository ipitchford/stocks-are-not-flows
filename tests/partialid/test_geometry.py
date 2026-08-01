import json

import numpy as np
import pytest

from housing_pressure.partialid import AssuranceScope, InvariantViolation, certify_focal_geometry


def test_exact_span_has_no_dual_discriminator() -> None:
    focal = np.asarray((1.0, 2.0, 3.0))
    nuisance = np.asarray(((0.5, 0.0), (1.0, 1.0), (1.5, -1.0)))

    certificate = certify_focal_geometry(
        focal,
        nuisance,
        focal_name="top_resource",
        nuisance_names=("scaled_focal", "rival"),
    )

    assert certificate.assurance_scope is AssuranceScope.DESIGN_INPUT_GEOMETRY_ONLY
    assert certificate.focal_in_nuisance_span
    assert not certificate.focal_identified_against_admitted_span
    assert certificate.dual_discriminator is None
    assert certificate.augmented_rank == certificate.nuisance_rank
    assert certificate.residual_norm < certificate.effective_span_tolerance
    assert certificate.to_dict()["interpretation_ceiling"].endswith(
        "not an empirical England bound."
    )
    json.dumps(certificate.to_dict(), allow_nan=False)


def test_identifiable_column_returns_unit_loading_annihilating_discriminator() -> None:
    focal = np.asarray((1.0, 0.0, 0.0))
    nuisance = np.asarray(((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)))

    certificate = certify_focal_geometry(focal, nuisance)

    assert certificate.focal_identified_against_admitted_span
    assert not certificate.focal_in_nuisance_span
    assert certificate.augmented_rank == certificate.nuisance_rank + 1
    discriminator = certificate.dual_discriminator
    assert discriminator is not None
    weights = np.asarray(discriminator.weights)
    assert weights @ focal == pytest.approx(1.0)
    np.testing.assert_allclose(weights @ nuisance, (0.0, 0.0), atol=1e-14)
    assert discriminator.nuisance_annihilation_norm == pytest.approx(0.0)


def test_zero_column_is_correctly_classified_as_in_every_span() -> None:
    certificate = certify_focal_geometry(
        np.zeros(2),
        np.empty((2, 0)),
        nuisance_names=(),
    )

    assert certificate.focal_in_nuisance_span
    assert certificate.relative_residual_norm == 0.0
    assert certificate.dual_discriminator is None


def test_malformed_tolerance_raises_typed_invariant_violation() -> None:
    with pytest.raises(InvariantViolation, match="finite numeric scalar"):
        certify_focal_geometry((1.0,), np.empty((1, 0)), absolute_tolerance="not-a-number")


def test_span_decision_is_invariant_to_nonzero_column_rescaling() -> None:
    focal = np.asarray((1.0, 2.0, 3.0))
    ordinary = certify_focal_geometry(focal, focal[:, None])
    tiny_units = certify_focal_geometry(focal, (1e-200 * focal)[:, None])
    tiny_focal_units = certify_focal_geometry(1e-200 * focal, focal[:, None])

    assert ordinary.focal_in_nuisance_span
    assert tiny_units.focal_in_nuisance_span
    assert tiny_focal_units.focal_in_nuisance_span
    assert tiny_units.nuisance_column_norms[0] == pytest.approx(1e-200 * np.linalg.norm(focal))
    assert tiny_units.to_dict()["singular_values_basis"] == (
        "INDIVIDUALLY_COLUMN_NORMALIZED_DESIGN"
    )
    assert tiny_units.to_dict()["span_test_basis"] == (
        "RELATIVE_RESIDUAL_OF_UNIT_NORM_FOCAL_COLUMN"
    )


def test_tiny_identifiable_focal_column_has_stable_dual_witness() -> None:
    focal = 1e-200 * np.asarray((1.0, 0.0))
    nuisance = np.asarray(((0.0,), (1.0,)))

    certificate = certify_focal_geometry(focal, nuisance)

    assert certificate.focal_identified_against_admitted_span
    assert certificate.dual_discriminator is not None
    weights = np.asarray(certificate.dual_discriminator.weights)
    assert np.all(np.isfinite(weights))
    assert weights @ focal == pytest.approx(1.0)
    assert weights @ nuisance == pytest.approx((0.0,))
