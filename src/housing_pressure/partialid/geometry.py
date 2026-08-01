"""Deterministic focal-versus-rival column-space diagnostics.

The functions in this module inspect supplied design columns only.  They do not
claim that those columns are empirically valid for England, nor do they turn a
synthetic response design into a causal estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray

from .errors import InvariantViolation


FloatArray = NDArray[np.float64]


class AssuranceScope(str, Enum):
    """Machine-readable ceiling on the interpretation of a result."""

    DESIGN_INPUT_GEOMETRY_ONLY = "DESIGN_INPUT_GEOMETRY_ONLY"
    CONDITIONAL_RESPONSE_SET_ONLY = "CONDITIONAL_RESPONSE_SET_ONLY"


@dataclass(frozen=True)
class DualDiscriminator:
    """A moment contrast that annihilates the admitted nuisance span.

    The weights ``d`` are normalized so that ``d' focal = 1``.  Consequently,
    ``d' nuisance = 0`` is a direct certificate that the supplied focal column
    has a direction outside the admitted nuisance/rival span.
    """

    weights: tuple[float, ...]
    focal_loading: float
    nuisance_annihilation_norm: float
    maximum_absolute_nuisance_loading: float

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "weights": list(self.weights),
            "focal_loading": self.focal_loading,
            "nuisance_annihilation_norm": self.nuisance_annihilation_norm,
            "maximum_absolute_nuisance_loading": self.maximum_absolute_nuisance_loading,
        }


@dataclass(frozen=True)
class DesignGeometryCertificate:
    """Auditable certificate for focal identification against an admitted span."""

    assurance_scope: AssuranceScope
    focal_name: str
    nuisance_names: tuple[str, ...]
    n_moments: int
    nuisance_rank: int
    augmented_rank: int
    focal_norm: float
    projection_norm: float
    residual_norm: float
    relative_residual_norm: float
    absolute_tolerance: float
    relative_tolerance: float
    effective_span_tolerance: float
    focal_in_nuisance_span: bool
    focal_identified_against_admitted_span: bool
    nuisance_column_norms: tuple[float, ...]
    normalized_projection_coefficients: tuple[float, ...]
    nuisance_singular_values: tuple[float, ...]
    augmented_singular_values: tuple[float, ...]
    dual_discriminator: DualDiscriminator | None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "assurance_scope": self.assurance_scope.value,
            "focal_name": self.focal_name,
            "nuisance_names": list(self.nuisance_names),
            "n_moments": self.n_moments,
            "nuisance_rank": self.nuisance_rank,
            "augmented_rank": self.augmented_rank,
            "focal_norm": self.focal_norm,
            "projection_norm": self.projection_norm,
            "residual_norm": self.residual_norm,
            "relative_residual_norm": self.relative_residual_norm,
            "absolute_tolerance": self.absolute_tolerance,
            "relative_tolerance": self.relative_tolerance,
            "effective_span_tolerance": self.effective_span_tolerance,
            "focal_in_nuisance_span": self.focal_in_nuisance_span,
            "focal_identified_against_admitted_span": (self.focal_identified_against_admitted_span),
            "nuisance_column_norms": list(self.nuisance_column_norms),
            "normalized_projection_coefficients": list(self.normalized_projection_coefficients),
            "nuisance_singular_values": list(self.nuisance_singular_values),
            "augmented_singular_values": list(self.augmented_singular_values),
            "singular_values_basis": "INDIVIDUALLY_COLUMN_NORMALIZED_DESIGN",
            "span_test_basis": "RELATIVE_RESIDUAL_OF_UNIT_NORM_FOCAL_COLUMN",
            "dual_discriminator": (
                None if self.dual_discriminator is None else self.dual_discriminator.to_dict()
            ),
            "interpretation_ceiling": (
                "Deterministic geometry of supplied columns; not an empirical England bound."
            ),
        }


def certify_focal_geometry(
    focal_column: ArrayLike,
    nuisance_columns: ArrayLike,
    *,
    focal_name: str = "focal",
    nuisance_names: Sequence[str] | None = None,
    absolute_tolerance: float = 1e-10,
    relative_tolerance: float = 1e-10,
) -> DesignGeometryCertificate:
    """Certify whether a focal column lies in an admitted nuisance/rival span.

    Let ``f`` be the supplied focal column and ``N`` the supplied nuisance
    matrix.  The certificate computes the minimum-norm projection ``P_N f`` and
    residual ``r = (I - P_N) f``.  The focal direction is distinguishable from
    the admitted span exactly when that residual is nonzero, up to the declared
    numerical tolerance.

    When distinguishable, ``r / (r' f)`` is returned as a dual discriminator.
    It has unit focal loading and zero loading on every retained singular
    direction of ``N``.
    """

    focal = _finite_vector(focal_column, "focal_column")
    nuisance = _finite_matrix(nuisance_columns, "nuisance_columns")
    if nuisance.shape[0] != focal.size:
        raise InvariantViolation(
            "nuisance_columns row count must equal focal_column length: "
            f"{nuisance.shape[0]} != {focal.size}"
        )
    focal_label = _nonempty_name(focal_name, "focal_name")
    names = _column_names(nuisance_names, nuisance.shape[1])
    atol, rtol = _validated_tolerances(absolute_tolerance, relative_tolerance)

    nuisance_norms = np.asarray(
        [
            _stable_norm(nuisance[:, index], f"nuisance_columns[:, {index}]")
            for index in range(nuisance.shape[1])
        ]
    )
    normalized_nuisance = np.zeros_like(nuisance)
    nonzero_columns = nuisance_norms > 0.0
    normalized_nuisance[:, nonzero_columns] = (
        nuisance[:, nonzero_columns] / nuisance_norms[nonzero_columns]
    )

    nuisance_svd = _truncated_svd(normalized_nuisance, atol, rtol)
    normalized_coefficients = np.zeros(nuisance.shape[1], dtype=float)
    if nuisance_svd.rank:
        retained_u = nuisance_svd.left[:, : nuisance_svd.rank]
        retained_s = nuisance_svd.values[: nuisance_svd.rank]
        retained_vt = nuisance_svd.right_transpose[: nuisance_svd.rank, :]
        normalized_coefficients = retained_vt.T @ ((retained_u.T @ focal) / retained_s)

    projection = normalized_nuisance @ normalized_coefficients
    residual = focal - projection
    focal_norm = _stable_norm(focal, "focal_column")
    projection_norm = _stable_norm(projection, "focal projection")
    residual_norm = _stable_norm(residual, "focal projection residual")
    relative_residual = residual_norm / focal_norm if focal_norm > 0.0 else 0.0
    effective_tolerance = atol + rtol
    in_span = relative_residual <= effective_tolerance

    normalized_focal = focal / focal_norm if focal_norm > 0.0 else focal.copy()
    augmented = np.column_stack((normalized_nuisance, normalized_focal))
    augmented_svd = _truncated_svd(augmented, atol, rtol)
    discriminator = None
    if not in_span:
        if residual_norm <= 0.0:
            raise InvariantViolation(
                "a non-spanning focal column produced a non-positive residual norm"
            )
        unit_residual = residual / residual_norm
        weights = unit_residual / residual_norm
        if not np.all(np.isfinite(weights)):
            raise InvariantViolation("dual-discriminator weights exceed floating-point range")
        nuisance_loading = nuisance.T @ weights
        discriminator = DualDiscriminator(
            weights=tuple(float(value) for value in weights),
            focal_loading=float(weights @ focal),
            nuisance_annihilation_norm=_stable_norm(nuisance_loading, "dual nuisance loading"),
            maximum_absolute_nuisance_loading=(
                float(np.max(np.abs(nuisance_loading))) if nuisance_loading.size else 0.0
            ),
        )

    return DesignGeometryCertificate(
        assurance_scope=AssuranceScope.DESIGN_INPUT_GEOMETRY_ONLY,
        focal_name=focal_label,
        nuisance_names=names,
        n_moments=int(focal.size),
        nuisance_rank=nuisance_svd.rank,
        augmented_rank=augmented_svd.rank,
        focal_norm=focal_norm,
        projection_norm=projection_norm,
        residual_norm=residual_norm,
        relative_residual_norm=relative_residual,
        absolute_tolerance=atol,
        relative_tolerance=rtol,
        effective_span_tolerance=effective_tolerance,
        focal_in_nuisance_span=in_span,
        focal_identified_against_admitted_span=not in_span,
        nuisance_column_norms=tuple(float(value) for value in nuisance_norms),
        normalized_projection_coefficients=tuple(float(value) for value in normalized_coefficients),
        nuisance_singular_values=tuple(float(value) for value in nuisance_svd.values),
        augmented_singular_values=tuple(float(value) for value in augmented_svd.values),
        dual_discriminator=discriminator,
    )


@dataclass(frozen=True)
class _TruncatedSvd:
    left: FloatArray
    values: FloatArray
    right_transpose: FloatArray
    rank: int


def _truncated_svd(matrix: FloatArray, atol: float, rtol: float) -> _TruncatedSvd:
    left, values, right_transpose = np.linalg.svd(matrix, full_matrices=False)
    largest = float(values[0]) if values.size else 0.0
    threshold = max(atol, rtol * largest)
    rank = int(np.count_nonzero(values > threshold))
    return _TruncatedSvd(left, values, right_transpose, rank)


def _stable_norm(values: FloatArray, name: str) -> float:
    """Compute a Euclidean norm without avoidable intermediate overflow."""

    if values.size == 0:
        return 0.0
    scale = float(np.max(np.abs(values)))
    if scale == 0.0:
        return 0.0
    result = scale * float(np.linalg.norm(values / scale))
    if not math.isfinite(result):
        raise InvariantViolation(f"{name} Euclidean norm exceeds floating-point range")
    return result


def _finite_vector(values: ArrayLike, name: str) -> FloatArray:
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise InvariantViolation(f"{name} must be numeric: {exc}") from exc
    if array.ndim != 1 or array.size == 0:
        raise InvariantViolation(f"{name} must be a non-empty one-dimensional vector")
    if not np.all(np.isfinite(array)):
        raise InvariantViolation(f"{name} must contain only finite values")
    return array


def _finite_matrix(values: ArrayLike, name: str) -> FloatArray:
    try:
        array = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise InvariantViolation(f"{name} must be numeric: {exc}") from exc
    if array.ndim != 2 or array.shape[0] == 0:
        raise InvariantViolation(f"{name} must be a two-dimensional matrix with at least one row")
    if not np.all(np.isfinite(array)):
        raise InvariantViolation(f"{name} must contain only finite values")
    return array


def _validated_tolerances(absolute: float, relative: float) -> tuple[float, float]:
    atol = _numeric_scalar(absolute, "absolute_tolerance")
    rtol = _numeric_scalar(relative, "relative_tolerance")
    if atol < 0.0:
        raise InvariantViolation("absolute_tolerance must be finite and non-negative")
    if rtol < 0.0:
        raise InvariantViolation("relative_tolerance must be finite and non-negative")
    if atol == 0.0 and rtol == 0.0:
        raise InvariantViolation("at least one numerical tolerance must be positive")
    return atol, rtol


def _numeric_scalar(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise InvariantViolation(f"{field} must be a finite numeric scalar")
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise InvariantViolation(f"{field} must be a finite numeric scalar") from exc
    if not math.isfinite(converted):
        raise InvariantViolation(f"{field} must be a finite numeric scalar")
    return converted


def _column_names(names: Sequence[str] | None, count: int) -> tuple[str, ...]:
    if names is None:
        return tuple(f"nuisance_{index}" for index in range(count))
    if isinstance(names, (str, bytes)):
        raise InvariantViolation("nuisance_names must be a sequence of names, not a string")
    try:
        supplied = tuple(names)
    except TypeError as exc:
        raise InvariantViolation("nuisance_names must be a sequence of names") from exc
    result = tuple(
        _nonempty_name(name, f"nuisance_names[{index}]") for index, name in enumerate(supplied)
    )
    if len(result) != count:
        raise InvariantViolation(
            f"nuisance_names must contain one name per column: {len(result)} != {count}"
        )
    if len(result) != len(set(result)):
        raise InvariantViolation("nuisance_names must be unique")
    return result


def _nonempty_name(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvariantViolation(f"{field} must be a non-empty string")
    return value.strip()
