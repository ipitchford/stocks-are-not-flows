"""Housing-specific deterministic certificate for the post-IDENT-0 pivot."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
import re
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from housing_pressure.ident0.diagnostics import Ident0Config
from housing_pressure.ident0.observation_adapter import PublicCoreObservationAdapter
from housing_pressure.ident0.response_model import BLOCK_NAMES, TARGET_ROLE, LocalResponseModel
from housing_pressure.ident0.rivals import RIVAL_NAMES, simulate_all_rivals

from .errors import InvariantViolation
from .geometry import DesignGeometryCertificate, certify_focal_geometry


FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class MatrixSummary:
    rows: int
    columns: int
    rank: int
    singular_values: tuple[float, ...]
    condition_number: float | None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class HousingDesignAudit:
    schema_version: str
    decision: str
    pass_unique_attribution_authorized: bool
    empirical_england_bound: bool
    authoritative_ident0_decision: str
    authoritative_ident0_report_sha256: str
    focal_name: str
    maintained_names: tuple[str, ...]
    constructed_rival_names: tuple[str, ...]
    target_observations: int
    public_unit_derivative_control_max_abs: float
    maintained_public_unit: MatrixSummary
    augmented_public_unit: MatrixSummary
    maintained_scaled: MatrixSummary
    augmented_scaled: MatrixSummary
    public_unit_geometry: DesignGeometryCertificate
    scaled_geometry: DesignGeometryCertificate
    assurance_boundary: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["public_unit_geometry"] = self.public_unit_geometry.to_dict()
        payload["scaled_geometry"] = self.scaled_geometry.to_dict()
        return payload


def _matrix_summary(matrix: FloatArray) -> MatrixSummary:
    if matrix.ndim != 2 or not matrix.size or not np.all(np.isfinite(matrix)):
        raise InvariantViolation("design certificate matrix must be finite and non-empty")
    singular = np.linalg.svd(matrix, compute_uv=False)
    rank = int(np.linalg.matrix_rank(matrix))
    condition = None
    if rank == matrix.shape[1] and singular[-1] > 0.0:
        condition = float(singular[0] / singular[-1])
    return MatrixSummary(
        rows=int(matrix.shape[0]),
        columns=int(matrix.shape[1]),
        rank=rank,
        singular_values=tuple(float(value) for value in singular),
        condition_number=condition,
    )


def _public_unit_jacobian(
    model: LocalResponseModel,
    adapter: PublicCoreObservationAdapter,
) -> FloatArray:
    internal = model.analytic_jacobian(TARGET_ROLE).copy()
    schedule = model.observation_schedule(TARGET_ROLE)
    if internal.shape[0] != len(schedule):
        raise InvariantViolation("target schedule and analytic Jacobian do not align")
    factors = np.ones(len(schedule), dtype=float)
    for index, item in enumerate(schedule):
        if item.adapter == "nominal_rent_level_from_log_pct":
            factors[index] = adapter.baselines["median_nominal_weekly_rent_gbp"] / 100.0
        elif item.adapter not in {
            "identity_deviation",
            "owner_share_level",
            "private_renter_share_level",
        }:
            raise InvariantViolation(
                f"target {item.observation_id} has an unknown derivative adapter"
            )
    result = factors[:, np.newaxis] * internal
    if not np.all(np.isfinite(result)):
        raise InvariantViolation("public-unit Jacobian contains non-finite values")
    return result


def _finite_difference_control(
    model: LocalResponseModel,
    adapter: PublicCoreObservationAdapter,
    analytic: FloatArray,
    *,
    step: float = 1e-5,
) -> float:
    zero = np.zeros(len(BLOCK_NAMES), dtype=float)
    columns: list[FloatArray] = []
    for index in range(len(BLOCK_NAMES)):
        delta = np.zeros(len(BLOCK_NAMES), dtype=float)
        delta[index] = step
        upper = adapter.vector(model, zero + delta, TARGET_ROLE).values
        lower = adapter.vector(model, zero - delta, TARGET_ROLE).values
        columns.append((upper - lower) / (2.0 * step))
    numerical = np.column_stack(columns)
    difference = float(np.max(np.abs(numerical - analytic)))
    if not math.isfinite(difference) or difference > 1e-7:
        raise InvariantViolation(
            f"public-unit analytic derivative failed its central-difference control: {difference}"
        )
    return difference


def build_housing_design_audit(
    config: Ident0Config,
    authoritative_ident0_report: Mapping[str, object],
    *,
    authoritative_ident0_report_sha256: str,
    absolute_tolerance: float = 1e-10,
    relative_tolerance: float = 1e-10,
) -> HousingDesignAudit:
    """Certify the exact synthetic public-core geometry after the failed gate."""

    if authoritative_ident0_report.get("decision") != "FAIL-IDENT-0":
        raise InvariantViolation("design pivot requires the authoritative FAIL-IDENT-0 report")
    if authoritative_ident0_report.get("pass_ident0_authorized") is not False:
        raise InvariantViolation("authoritative IDENT-0 report has an invalid pass flag")
    if not isinstance(authoritative_ident0_report_sha256, str) or not re.fullmatch(
        r"[0-9a-f]{64}", authoritative_ident0_report_sha256
    ):
        raise InvariantViolation("authoritative IDENT-0 report SHA-256 must be a 64-digit string")
    if BLOCK_NAMES[0] != "z_top" or tuple(RIVAL_NAMES) != (
        "social_comparison",
        "institutional_entry",
        "rental_segmentation",
        "planning_restriction",
    ):
        raise InvariantViolation("maintained or rival design order has drifted")

    model = LocalResponseModel.baseline()
    adapter = PublicCoreObservationAdapter(config)
    neutral = adapter.vector(model, np.zeros(len(BLOCK_NAMES)), TARGET_ROLE)
    public_jacobian = _public_unit_jacobian(model, adapter)
    derivative_difference = _finite_difference_control(model, adapter, public_jacobian)
    rival_columns = np.column_stack(
        [
            adapter.vector_from_panel(model, simulation.panel, TARGET_ROLE).values - neutral.values
            for simulation in simulate_all_rivals(model)
        ]
    )
    if public_jacobian.shape != (57, 7) or rival_columns.shape != (57, 4):
        raise InvariantViolation(
            "registered target/rival matrices must have shapes (57, 7) and (57, 4)"
        )
    augmented = np.column_stack((public_jacobian, rival_columns))
    nuisance = np.column_stack((public_jacobian[:, 1:], rival_columns))
    nuisance_names = (*BLOCK_NAMES[1:], *RIVAL_NAMES)
    public_geometry = certify_focal_geometry(
        public_jacobian[:, 0],
        nuisance,
        focal_name=BLOCK_NAMES[0],
        nuisance_names=nuisance_names,
        absolute_tolerance=absolute_tolerance,
        relative_tolerance=relative_tolerance,
    )

    scales = adapter.scales_for(neutral)
    scaled_jacobian = public_jacobian / scales[:, np.newaxis]
    scaled_rivals = rival_columns / scales[:, np.newaxis]
    scaled_augmented = np.column_stack((scaled_jacobian, scaled_rivals))
    scaled_geometry = certify_focal_geometry(
        scaled_jacobian[:, 0],
        np.column_stack((scaled_jacobian[:, 1:], scaled_rivals)),
        focal_name=BLOCK_NAMES[0],
        nuisance_names=nuisance_names,
        absolute_tolerance=absolute_tolerance,
        relative_tolerance=relative_tolerance,
    )

    summaries = (
        _matrix_summary(public_jacobian),
        _matrix_summary(augmented),
        _matrix_summary(scaled_jacobian),
        _matrix_summary(scaled_augmented),
    )
    if summaries[0].rank != 7 or summaries[1].rank != 9:
        raise InvariantViolation("maintained or augmented public-unit rank has drifted")
    if summaries[2].rank != 7 or summaries[3].rank != 9:
        raise InvariantViolation("maintained or augmented scaled rank has drifted")
    if not public_geometry.focal_in_nuisance_span or not scaled_geometry.focal_in_nuisance_span:
        raise InvariantViolation("registered constructed rivals no longer span the focal column")

    return HousingDesignAudit(
        schema_version="0.1",
        decision="STOP-UNIQUE+GO-PARTIAL-ID-THEORY",
        pass_unique_attribution_authorized=False,
        empirical_england_bound=False,
        authoritative_ident0_decision="FAIL-IDENT-0",
        authoritative_ident0_report_sha256=authoritative_ident0_report_sha256,
        focal_name=BLOCK_NAMES[0],
        maintained_names=BLOCK_NAMES,
        constructed_rival_names=RIVAL_NAMES,
        target_observations=public_jacobian.shape[0],
        public_unit_derivative_control_max_abs=derivative_difference,
        maintained_public_unit=summaries[0],
        augmented_public_unit=summaries[1],
        maintained_scaled=summaries[2],
        augmented_scaled=summaries[3],
        public_unit_geometry=public_geometry,
        scaled_geometry=scaled_geometry,
        assurance_boundary=(
            "All maintained loadings, baselines, scales, and four rival signatures are synthetic design inputs.",
            "The four rivals are deliberately adversarial constructions, not a population sample.",
            "Full rank of the maintained seven-column matrix does not establish mechanism specificity.",
            "The span certificate is deterministic algebra inside the registered stress harness.",
            "No response set in this certificate is independently source-backed for England.",
            "The result cannot estimate a historical contribution, causal elasticity, or false-positive rate.",
        ),
    )


__all__ = ["HousingDesignAudit", "MatrixSummary", "build_housing_design_audit"]
