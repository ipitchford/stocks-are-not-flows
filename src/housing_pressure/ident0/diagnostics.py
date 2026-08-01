"""Generic numerical diagnostics for the IDENT-0 fail-fast gate.

The module deliberately knows nothing about the housing model.  Callers supply a
deterministic function ``f(theta) -> moments`` together with parameter bounds and
moment scales.  This keeps the identification tests reusable across the analytic
response design, MIN-EXEC, and later model variants.

All scientific checks return typed PASS/FAIL objects.  Invalid inputs raise
``InvariantViolation``; production behaviour never depends on Python assertions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import math
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import least_squares

from .errors import InvariantViolation


FloatArray = NDArray[np.float64]
ModelFunction = Callable[[FloatArray], ArrayLike]


class GateStatus(str, Enum):
    """Machine-readable scientific-gate status."""

    PASS = "PASS"
    FAIL = "FAIL"


@dataclass(frozen=True)
class CriterionResult:
    """One auditable gate criterion."""

    name: str
    status: GateStatus
    value: float | int | str | bool
    threshold: str
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


@dataclass(frozen=True)
class GateResult:
    """Aggregate PASS/FAIL result with no discretionary averaging."""

    gate: str
    status: GateStatus
    criteria: tuple[CriterionResult, ...]

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS

    @classmethod
    def from_criteria(cls, gate: str, criteria: Sequence[CriterionResult]) -> "GateResult":
        frozen = tuple(criteria)
        if not frozen:
            raise InvariantViolation(f"gate {gate!r} has no criteria")
        status = GateStatus.PASS if all(item.passed for item in frozen) else GateStatus.FAIL
        return cls(gate=gate, status=status, criteria=frozen)


@dataclass(frozen=True)
class Ident0Config:
    """Validated numerical contract loaded from ``configs/ident0.json``."""

    schema_version: str
    years: tuple[int, ...]
    seed: int
    finite_difference_steps: tuple[float, ...]
    rank_ratio_min: float
    condition_number_max: float
    local_rank_required_points: int
    local_rank_total_points: int
    sign_recovery_min: float
    coverage_min: float
    coverage_max: float
    null_false_positive_max: float
    rival_largest_block_max: float
    classification_min: float
    noiseless_case_pass_min: float
    optimiser_stability_min: float
    starts_per_fit: int
    same_basin_starts_min: int
    profile_grid_points: int
    profile_objective_difference_cutoff: float
    profile_max_width_fraction: float
    parameter_bounds: tuple[tuple[str, tuple[float, float]], ...]
    synthetic_moment_scales: tuple[tuple[str, float], ...]
    synthetic_baseline_levels: tuple[tuple[str, float], ...]
    economic_materiality: tuple[tuple[str, float], ...]

    @classmethod
    def from_mapping(cls, raw: Mapping[str, object]) -> "Ident0Config":
        required = {
            "schema_version",
            "years",
            "seed",
            "finite_difference_steps",
            "rank_ratio_min",
            "condition_number_max",
            "local_rank_required_points",
            "local_rank_total_points",
            "sign_recovery_min",
            "coverage_min",
            "coverage_max",
            "null_false_positive_max",
            "rival_largest_block_max",
            "classification_min",
            "noiseless_case_pass_min",
            "optimiser_stability_min",
            "starts_per_fit",
            "same_basin_starts_min",
            "profile_grid_points",
            "profile_objective_difference_cutoff",
            "profile_max_width_fraction",
            "parameter_bounds",
            "synthetic_moment_scales",
            "synthetic_baseline_levels",
            "economic_materiality",
        }
        missing = sorted(required.difference(raw))
        unknown = sorted(set(raw).difference(required))
        if missing:
            raise InvariantViolation(f"IDENT-0 config is missing keys: {missing}")
        if unknown:
            raise InvariantViolation(f"IDENT-0 config has unknown keys: {unknown}")

        try:
            year_values = _require_sequence(raw["years"], "years")
            if any(isinstance(value, bool) or not isinstance(value, int) for value in year_values):
                raise InvariantViolation("years must contain JSON integers")
            years = tuple(year_values)
            steps = tuple(
                _json_number(value, "finite_difference_steps")
                for value in _require_sequence(
                    raw["finite_difference_steps"], "finite_difference_steps"
                )
            )
            materiality_raw = raw["economic_materiality"]
            if not isinstance(materiality_raw, Mapping):
                raise InvariantViolation("economic_materiality must be a mapping")
            materiality = tuple(
                sorted(
                    (str(name), _json_number(value, f"economic_materiality[{name!r}]"))
                    for name, value in materiality_raw.items()
                )
            )
            bounds_raw = raw["parameter_bounds"]
            if not isinstance(bounds_raw, Mapping):
                raise InvariantViolation("parameter_bounds must be a mapping")
            parameter_bounds: list[tuple[str, tuple[float, float]]] = []
            for name, values in bounds_raw.items():
                pair = _require_sequence(values, f"parameter_bounds[{name!r}]")
                if len(pair) != 2:
                    raise InvariantViolation(
                        f"parameter_bounds[{name!r}] must contain [lower, upper]"
                    )
                parameter_bounds.append(
                    (
                        str(name),
                        (
                            _json_number(pair[0], f"parameter_bounds[{name!r}][0]"),
                            _json_number(pair[1], f"parameter_bounds[{name!r}][1]"),
                        ),
                    )
                )
            scales_raw = raw["synthetic_moment_scales"]
            if not isinstance(scales_raw, Mapping):
                raise InvariantViolation("synthetic_moment_scales must be a mapping")
            synthetic_scales = tuple(
                sorted(
                    (str(name), _json_number(value, f"synthetic_moment_scales[{name!r}]"))
                    for name, value in scales_raw.items()
                )
            )
            baselines_raw = raw["synthetic_baseline_levels"]
            if not isinstance(baselines_raw, Mapping):
                raise InvariantViolation("synthetic_baseline_levels must be a mapping")
            synthetic_baselines = tuple(
                sorted(
                    (
                        str(name),
                        _json_number(value, f"synthetic_baseline_levels[{name!r}]"),
                    )
                    for name, value in baselines_raw.items()
                )
            )
            config = cls(
                schema_version=str(raw["schema_version"]),
                years=years,
                seed=_json_integer(raw["seed"], "seed"),
                finite_difference_steps=steps,
                rank_ratio_min=_json_number(raw["rank_ratio_min"], "rank_ratio_min"),
                condition_number_max=_json_number(
                    raw["condition_number_max"], "condition_number_max"
                ),
                local_rank_required_points=_json_integer(
                    raw["local_rank_required_points"], "local_rank_required_points"
                ),
                local_rank_total_points=_json_integer(
                    raw["local_rank_total_points"], "local_rank_total_points"
                ),
                sign_recovery_min=_json_number(raw["sign_recovery_min"], "sign_recovery_min"),
                coverage_min=_json_number(raw["coverage_min"], "coverage_min"),
                coverage_max=_json_number(raw["coverage_max"], "coverage_max"),
                null_false_positive_max=_json_number(
                    raw["null_false_positive_max"], "null_false_positive_max"
                ),
                rival_largest_block_max=_json_number(
                    raw["rival_largest_block_max"], "rival_largest_block_max"
                ),
                classification_min=_json_number(raw["classification_min"], "classification_min"),
                noiseless_case_pass_min=_json_number(
                    raw["noiseless_case_pass_min"], "noiseless_case_pass_min"
                ),
                optimiser_stability_min=_json_number(
                    raw["optimiser_stability_min"], "optimiser_stability_min"
                ),
                starts_per_fit=_json_integer(raw["starts_per_fit"], "starts_per_fit"),
                same_basin_starts_min=_json_integer(
                    raw["same_basin_starts_min"], "same_basin_starts_min"
                ),
                profile_grid_points=_json_integer(
                    raw["profile_grid_points"], "profile_grid_points"
                ),
                profile_objective_difference_cutoff=_json_number(
                    raw["profile_objective_difference_cutoff"],
                    "profile_objective_difference_cutoff",
                ),
                profile_max_width_fraction=_json_number(
                    raw["profile_max_width_fraction"], "profile_max_width_fraction"
                ),
                parameter_bounds=tuple(parameter_bounds),
                synthetic_moment_scales=synthetic_scales,
                synthetic_baseline_levels=synthetic_baselines,
                economic_materiality=materiality,
            )
        except (TypeError, ValueError) as exc:
            raise InvariantViolation(f"IDENT-0 config contains an invalid value: {exc}") from exc
        config.validate()
        return config

    def validate(self) -> None:
        if not self.schema_version.strip():
            raise InvariantViolation("schema_version must be non-empty")
        if not self.years or any(isinstance(year, bool) for year in self.years):
            raise InvariantViolation("years must contain integer calendar years")
        if any(b <= a for a, b in zip(self.years, self.years[1:])):
            raise InvariantViolation("years must be strictly increasing and unique")
        if self.seed < 0:
            raise InvariantViolation("seed must be non-negative")

        required_steps = np.asarray((0.005, 0.01, 0.02), dtype=float)
        supplied_steps = np.asarray(self.finite_difference_steps, dtype=float)
        if supplied_steps.shape != required_steps.shape or not np.allclose(
            supplied_steps, required_steps, rtol=0.0, atol=1e-12
        ):
            raise InvariantViolation(
                "finite_difference_steps must be exactly [0.005, 0.01, 0.02] in increasing order"
            )
        if not (0.0 < self.rank_ratio_min <= 1.0):
            raise InvariantViolation("rank_ratio_min must be in (0, 1]")
        if not math.isfinite(self.condition_number_max) or self.condition_number_max < 1.0:
            raise InvariantViolation("condition_number_max must be finite and at least 1")
        if self.local_rank_total_points <= 0:
            raise InvariantViolation("local_rank_total_points must be positive")
        if not 1 <= self.local_rank_required_points <= self.local_rank_total_points:
            raise InvariantViolation(
                "local_rank_required_points must be between 1 and local_rank_total_points"
            )

        _validate_rate("sign_recovery_min", self.sign_recovery_min)
        _validate_rate("coverage_min", self.coverage_min)
        _validate_rate("coverage_max", self.coverage_max)
        _validate_rate("null_false_positive_max", self.null_false_positive_max)
        _validate_rate("rival_largest_block_max", self.rival_largest_block_max)
        _validate_rate("classification_min", self.classification_min)
        _validate_rate("noiseless_case_pass_min", self.noiseless_case_pass_min)
        _validate_rate("optimiser_stability_min", self.optimiser_stability_min)
        if self.starts_per_fit <= 0:
            raise InvariantViolation("starts_per_fit must be positive")
        if not 1 <= self.same_basin_starts_min <= self.starts_per_fit:
            raise InvariantViolation(
                "same_basin_starts_min must lie between one and starts_per_fit"
            )
        if self.profile_grid_points < 3 or self.profile_grid_points % 2 == 0:
            raise InvariantViolation("profile_grid_points must be an odd integer at least 3")
        if (
            not math.isfinite(self.profile_objective_difference_cutoff)
            or self.profile_objective_difference_cutoff < 0.0
        ):
            raise InvariantViolation(
                "profile_objective_difference_cutoff must be finite and non-negative"
            )
        _validate_rate("profile_max_width_fraction", self.profile_max_width_fraction)
        if not self.parameter_bounds:
            raise InvariantViolation("parameter_bounds cannot be empty")
        bound_names = [name for name, _ in self.parameter_bounds]
        if len(bound_names) != len(set(bound_names)) or any(not name for name in bound_names):
            raise InvariantViolation("parameter_bounds names must be non-empty and unique")
        for name, (lower, upper) in self.parameter_bounds:
            if not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower:
                raise InvariantViolation(
                    f"parameter_bounds[{name!r}] must be finite and increasing"
                )
        if not self.synthetic_moment_scales:
            raise InvariantViolation("synthetic_moment_scales cannot be empty")
        scale_names = [name for name, _ in self.synthetic_moment_scales]
        if len(scale_names) != len(set(scale_names)) or any(not name for name in scale_names):
            raise InvariantViolation("synthetic_moment_scales names must be non-empty and unique")
        for name, value in self.synthetic_moment_scales:
            if not math.isfinite(value) or value <= 0.0:
                raise InvariantViolation(
                    f"synthetic_moment_scales[{name!r}] must be finite and positive"
                )
        required_baselines = {
            "owner_share_25_44_pct",
            "private_renter_share_25_44_pct",
            "median_nominal_weekly_rent_gbp",
        }
        baseline_names = [name for name, _ in self.synthetic_baseline_levels]
        if set(baseline_names) != required_baselines:
            raise InvariantViolation(
                "synthetic_baseline_levels must contain exactly "
                + ", ".join(sorted(required_baselines))
            )
        if len(baseline_names) != len(set(baseline_names)):
            raise InvariantViolation("synthetic_baseline_levels names must be unique")
        for name, value in self.synthetic_baseline_levels:
            if not math.isfinite(value) or value <= 0.0:
                raise InvariantViolation(
                    f"synthetic_baseline_levels[{name!r}] must be finite and positive"
                )
        baseline_map = dict(self.synthetic_baseline_levels)
        if baseline_map["owner_share_25_44_pct"] >= 100.0:
            raise InvariantViolation("synthetic owner share baseline must be below 100")
        if baseline_map["private_renter_share_25_44_pct"] >= 100.0:
            raise InvariantViolation("synthetic renter share baseline must be below 100")
        if self.coverage_min > self.coverage_max:
            raise InvariantViolation("coverage_min cannot exceed coverage_max")
        if not self.economic_materiality:
            raise InvariantViolation("economic_materiality cannot be empty")
        names = [name for name, _ in self.economic_materiality]
        if len(names) != len(set(names)):
            raise InvariantViolation("economic_materiality names must be unique")
        for name, value in self.economic_materiality:
            if not name or not math.isfinite(value) or value <= 0.0:
                raise InvariantViolation(
                    f"economic_materiality[{name!r}] must be finite and positive"
                )


def load_config(path: str | Path) -> Ident0Config:
    """Load and strictly validate an IDENT-0 JSON configuration."""

    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except OSError as exc:
        raise InvariantViolation(f"cannot read IDENT-0 config {config_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InvariantViolation(f"invalid JSON in IDENT-0 config {config_path}: {exc}") from exc
    if not isinstance(raw, Mapping):
        raise InvariantViolation("IDENT-0 config root must be a JSON object")
    return Ident0Config.from_mapping(raw)


@dataclass(frozen=True)
class ParameterBounds:
    """Named finite parameter box used for scaling and bounded optimization."""

    names: tuple[str, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.names:
            raise InvariantViolation("parameter bounds must contain at least one parameter")
        if len(set(self.names)) != len(self.names) or any(not name for name in self.names):
            raise InvariantViolation("parameter names must be non-empty and unique")
        if len(self.lower) != len(self.names) or len(self.upper) != len(self.names):
            raise InvariantViolation("parameter names, lower bounds, and upper bounds must align")
        lower = np.asarray(self.lower, dtype=float)
        upper = np.asarray(self.upper, dtype=float)
        if not np.all(np.isfinite(lower)) or not np.all(np.isfinite(upper)):
            raise InvariantViolation("parameter bounds must be finite")
        if np.any(upper <= lower):
            raise InvariantViolation("every upper bound must be strictly above its lower bound")

    @property
    def dimension(self) -> int:
        return len(self.names)

    @property
    def lower_array(self) -> FloatArray:
        return np.asarray(self.lower, dtype=float)

    @property
    def upper_array(self) -> FloatArray:
        return np.asarray(self.upper, dtype=float)

    @property
    def ranges(self) -> FloatArray:
        return self.upper_array - self.lower_array

    def validate_point(self, values: ArrayLike, *, label: str = "parameter point") -> FloatArray:
        point = _as_1d_float(label, values, expected=self.dimension)
        if np.any(point < self.lower_array) or np.any(point > self.upper_array):
            raise InvariantViolation(f"{label} lies outside the declared parameter bounds")
        return point

    def normalize(self, values: ArrayLike) -> FloatArray:
        point = self.validate_point(values)
        return (point - self.lower_array) / self.ranges

    def denormalize(self, values: ArrayLike) -> FloatArray:
        normalized = _as_1d_float("normalized parameter point", values, expected=self.dimension)
        if np.any(normalized < 0.0) or np.any(normalized > 1.0):
            raise InvariantViolation("normalized parameter point must lie in [0, 1]")
        return self.lower_array + normalized * self.ranges


@dataclass(frozen=True)
class JacobianEstimate:
    """Central-difference estimate with respect to normalized parameters."""

    step_fraction: float
    matrix: FloatArray
    baseline_moments: FloatArray


@dataclass(frozen=True)
class SvdDiagnostic:
    """Rank and conditioning diagnostic for one Jacobian."""

    rows: int
    columns: int
    singular_values: tuple[float, ...]
    rank: int
    smallest_largest_ratio: float
    condition_number: float
    status: GateStatus
    detail: str

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


@dataclass(frozen=True)
class ColumnAnglePair:
    left: str
    right: str
    absolute_cosine: float
    acute_angle_degrees: float


@dataclass(frozen=True)
class ColumnAngleDiagnostic:
    """Pairwise acute angles between scaled Jacobian columns."""

    pairs: tuple[ColumnAnglePair, ...]
    zero_columns: tuple[str, ...]
    maximum_absolute_cosine: float
    minimum_acute_angle_degrees: float
    status: GateStatus
    detail: str

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


@dataclass(frozen=True)
class JacobianSweepDiagnostic:
    """Finite-difference stability at all preregistered scaled steps."""

    estimates: tuple[JacobianEstimate, ...]
    svd: tuple[SvdDiagnostic, ...]
    angles: tuple[ColumnAngleDiagnostic, ...]
    rank_invariant: bool
    status: GateStatus
    gate: GateResult

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


def central_difference_jacobian(
    function: ModelFunction,
    theta: ArrayLike,
    bounds: ParameterBounds,
    *,
    step_fraction: float,
    moment_scale: ArrayLike | None = None,
) -> JacobianEstimate:
    """Compute a central Jacobian in normalized parameter-range units.

    A perturbation of ``step_fraction`` means that physical parameter ``j`` is
    moved by ``step_fraction * (upper[j] - lower[j])``.  The denominator is the
    normalized displacement, so columns are derivatives with respect to a unit
    move across each declared parameter range.  Moments are divided by
    ``moment_scale`` when supplied.
    """

    if not math.isfinite(step_fraction) or step_fraction <= 0.0:
        raise InvariantViolation("step_fraction must be finite and positive")
    point = bounds.validate_point(theta)
    baseline = _evaluate_model(function, point, label="baseline")
    scales = _validate_moment_scale(moment_scale, baseline.size)
    jacobian = np.empty((baseline.size, bounds.dimension), dtype=float)

    for index, width in enumerate(bounds.ranges):
        physical_step = step_fraction * width
        left = point.copy()
        right = point.copy()
        left[index] -= physical_step
        right[index] += physical_step
        if left[index] < bounds.lower[index] or right[index] > bounds.upper[index]:
            raise InvariantViolation(
                f"central step {step_fraction:g} for {bounds.names[index]!r} exits bounds; "
                "use an interior evaluation point rather than a one-sided derivative"
            )
        minus = _evaluate_model(function, left, label=f"minus {bounds.names[index]}")
        plus = _evaluate_model(function, right, label=f"plus {bounds.names[index]}")
        if minus.size != baseline.size or plus.size != baseline.size:
            raise InvariantViolation("model output dimension changes under finite differences")
        jacobian[:, index] = ((plus - minus) / scales) / (2.0 * step_fraction)

    if not np.all(np.isfinite(jacobian)):
        raise InvariantViolation("finite-difference Jacobian contains non-finite values")
    return JacobianEstimate(
        step_fraction=float(step_fraction),
        matrix=jacobian,
        baseline_moments=baseline,
    )


def svd_diagnostics(
    jacobian: ArrayLike,
    *,
    rank_ratio_min: float,
    condition_number_max: float,
) -> SvdDiagnostic:
    """Report scaled singular values, numerical rank, and conditioning."""

    matrix = _as_2d_float("jacobian", jacobian)
    if matrix.shape[1] == 0 or matrix.shape[0] == 0:
        raise InvariantViolation("jacobian must have at least one row and one column")
    if not (0.0 < rank_ratio_min <= 1.0):
        raise InvariantViolation("rank_ratio_min must be in (0, 1]")
    if not math.isfinite(condition_number_max) or condition_number_max < 1.0:
        raise InvariantViolation("condition_number_max must be finite and at least 1")

    singular = np.linalg.svd(matrix, compute_uv=False)
    largest = float(singular[0]) if singular.size else 0.0
    required_rank = matrix.shape[1]
    if largest <= 0.0:
        rank = 0
        ratio = 0.0
        condition = math.inf
    else:
        threshold = largest * rank_ratio_min
        rank = int(np.count_nonzero(singular >= threshold))
        if matrix.shape[0] < matrix.shape[1] or singular.size < required_rank:
            ratio = 0.0
            condition = math.inf
        else:
            smallest = float(singular[required_rank - 1])
            ratio = smallest / largest
            condition = math.inf if smallest <= 0.0 else largest / smallest

    passed = rank == required_rank and ratio >= rank_ratio_min and condition <= condition_number_max
    detail = (
        f"rank {rank}/{required_rank}; sigma_min/sigma_max={ratio:.6g}; condition={condition:.6g}"
    )
    return SvdDiagnostic(
        rows=matrix.shape[0],
        columns=matrix.shape[1],
        singular_values=tuple(float(value) for value in singular),
        rank=rank,
        smallest_largest_ratio=ratio,
        condition_number=condition,
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        detail=detail,
    )


def column_angle_diagnostics(
    jacobian: ArrayLike,
    *,
    names: Sequence[str] | None = None,
    maximum_absolute_cosine: float | None = None,
) -> ColumnAngleDiagnostic:
    """Compute acute column angles; optional cosine threshold makes it a gate."""

    matrix = _as_2d_float("jacobian", jacobian)
    columns = matrix.shape[1]
    if columns == 0:
        raise InvariantViolation("jacobian must contain at least one column")
    labels = _validate_names(names, columns, prefix="parameter")
    if maximum_absolute_cosine is not None and not (0.0 <= maximum_absolute_cosine <= 1.0):
        raise InvariantViolation("maximum_absolute_cosine must be in [0, 1]")

    norms = np.linalg.norm(matrix, axis=0)
    zero = tuple(labels[index] for index, value in enumerate(norms) if value <= 0.0)
    pairs: list[ColumnAnglePair] = []
    for left in range(columns):
        for right in range(left + 1, columns):
            if norms[left] <= 0.0 or norms[right] <= 0.0:
                cosine = 1.0
                angle = 0.0
            else:
                raw = float(
                    np.dot(matrix[:, left], matrix[:, right]) / (norms[left] * norms[right])
                )
                cosine = min(1.0, max(0.0, abs(raw)))
                angle = math.degrees(math.acos(cosine))
            pairs.append(
                ColumnAnglePair(
                    left=labels[left],
                    right=labels[right],
                    absolute_cosine=cosine,
                    acute_angle_degrees=angle,
                )
            )

    observed_max = max((pair.absolute_cosine for pair in pairs), default=0.0)
    observed_min_angle = min((pair.acute_angle_degrees for pair in pairs), default=90.0)
    passed = not zero and (
        maximum_absolute_cosine is None or observed_max <= maximum_absolute_cosine
    )
    detail = f"zero columns={list(zero)}; max |cosine|={observed_max:.6g}"
    return ColumnAngleDiagnostic(
        pairs=tuple(pairs),
        zero_columns=zero,
        maximum_absolute_cosine=observed_max,
        minimum_acute_angle_degrees=observed_min_angle,
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        detail=detail,
    )


def jacobian_step_sweep(
    function: ModelFunction,
    theta: ArrayLike,
    bounds: ParameterBounds,
    config: Ident0Config,
    *,
    moment_scale: ArrayLike | None = None,
    maximum_absolute_cosine: float | None = None,
) -> JacobianSweepDiagnostic:
    """Run central Jacobians at 0.5%, 1%, and 2% scaled steps."""

    estimates: list[JacobianEstimate] = []
    svd_items: list[SvdDiagnostic] = []
    angle_items: list[ColumnAngleDiagnostic] = []
    for step in config.finite_difference_steps:
        estimate = central_difference_jacobian(
            function,
            theta,
            bounds,
            step_fraction=step,
            moment_scale=moment_scale,
        )
        estimates.append(estimate)
        svd_items.append(
            svd_diagnostics(
                estimate.matrix,
                rank_ratio_min=config.rank_ratio_min,
                condition_number_max=config.condition_number_max,
            )
        )
        angle_items.append(
            column_angle_diagnostics(
                estimate.matrix,
                names=bounds.names,
                maximum_absolute_cosine=maximum_absolute_cosine,
            )
        )

    ranks = tuple(item.rank for item in svd_items)
    invariant = len(set(ranks)) == 1
    criteria = [
        CriterionResult(
            name=f"svd_step_{estimate.step_fraction:g}",
            status=diagnostic.status,
            value=diagnostic.smallest_largest_ratio,
            threshold=(
                f"full rank, ratio >= {config.rank_ratio_min:g}, "
                f"condition <= {config.condition_number_max:g}"
            ),
            detail=diagnostic.detail,
        )
        for estimate, diagnostic in zip(estimates, svd_items)
    ]
    criteria.append(
        CriterionResult(
            name="rank_invariant_across_steps",
            status=GateStatus.PASS if invariant else GateStatus.FAIL,
            value=str(ranks),
            threshold="identical rank at 0.5%, 1%, and 2% steps",
        )
    )
    if maximum_absolute_cosine is not None:
        criteria.extend(
            CriterionResult(
                name=f"column_angles_step_{estimate.step_fraction:g}",
                status=diagnostic.status,
                value=diagnostic.maximum_absolute_cosine,
                threshold=f"maximum |cosine| <= {maximum_absolute_cosine:g}",
                detail=diagnostic.detail,
            )
            for estimate, diagnostic in zip(estimates, angle_items)
        )
    gate = GateResult.from_criteria("jacobian_step_sweep", criteria)
    return JacobianSweepDiagnostic(
        estimates=tuple(estimates),
        svd=tuple(svd_items),
        angles=tuple(angle_items),
        rank_invariant=invariant,
        status=gate.status,
        gate=gate,
    )


@dataclass(frozen=True)
class LocalIdentificationSummary:
    points_total: int
    points_passing: int
    required_points: int
    selected_point: int
    selected_point_passed: bool
    diagnostics: tuple[JacobianSweepDiagnostic, ...]
    status: GateStatus
    gate: GateResult

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


def local_identification_summary(
    function: ModelFunction,
    points: ArrayLike,
    bounds: ParameterBounds,
    config: Ident0Config,
    *,
    moment_scale: ArrayLike | None = None,
    selected_point: int = 0,
    maximum_absolute_cosine: float | None = None,
) -> LocalIdentificationSummary:
    """Evaluate the preregistered local-rank rule on a deterministic point set."""

    point_matrix = _as_2d_float("local-identification points", points)
    if point_matrix.shape[1] != bounds.dimension:
        raise InvariantViolation("local-identification point dimension does not match bounds")
    if point_matrix.shape[0] != config.local_rank_total_points:
        raise InvariantViolation(
            f"expected {config.local_rank_total_points} local points, got {point_matrix.shape[0]}"
        )
    if not 0 <= selected_point < point_matrix.shape[0]:
        raise InvariantViolation("selected_point index is out of range")

    diagnostics = tuple(
        jacobian_step_sweep(
            function,
            bounds.validate_point(point, label=f"local point {index}"),
            bounds,
            config,
            moment_scale=moment_scale,
            maximum_absolute_cosine=maximum_absolute_cosine,
        )
        for index, point in enumerate(point_matrix)
    )
    passing = sum(item.passed for item in diagnostics)
    selected_passed = diagnostics[selected_point].passed
    criteria = (
        CriterionResult(
            name="required_local_points",
            status=(
                GateStatus.PASS if passing >= config.local_rank_required_points else GateStatus.FAIL
            ),
            value=passing,
            threshold=f">= {config.local_rank_required_points} of {point_matrix.shape[0]}",
        ),
        CriterionResult(
            name="selected_point",
            status=GateStatus.PASS if selected_passed else GateStatus.FAIL,
            value=selected_passed,
            threshold="selected empirical point passes",
        ),
    )
    gate = GateResult.from_criteria("local_identification", criteria)
    return LocalIdentificationSummary(
        points_total=point_matrix.shape[0],
        points_passing=passing,
        required_points=config.local_rank_required_points,
        selected_point=selected_point,
        selected_point_passed=selected_passed,
        diagnostics=diagnostics,
        status=gate.status,
        gate=gate,
    )


@dataclass(frozen=True)
class FitAttempt:
    start_index: int
    start: tuple[float, ...]
    estimate: tuple[float, ...]
    objective: float
    success: bool
    status_code: int
    message: str
    evaluations: int
    optimality: float


@dataclass(frozen=True)
class RecoveryResult:
    attempts: tuple[FitAttempt, ...]
    best_index: int | None
    successful_starts: int
    same_basin_starts: int
    same_basin_fraction: float
    status: GateStatus
    gate: GateResult

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS

    @property
    def best(self) -> FitAttempt | None:
        return None if self.best_index is None else self.attempts[self.best_index]


def recover_multistart(
    function: ModelFunction,
    observed_moments: ArrayLike,
    bounds: ParameterBounds,
    starts: ArrayLike,
    *,
    moment_scale: ArrayLike | None = None,
    stability_min: float = 0.95,
    minimum_same_basin_starts: int | None = None,
    basin_relative_tolerance: float = 1e-6,
    max_nfev: int = 2_000,
) -> RecoveryResult:
    """Recover parameters by bounded nonlinear least squares from every start."""

    observed = _as_1d_float("observed moments", observed_moments)
    scales = _validate_moment_scale(moment_scale, observed.size)
    start_matrix = _as_2d_float("optimizer starts", starts)
    if start_matrix.shape[1] != bounds.dimension:
        raise InvariantViolation("optimizer-start dimension does not match parameter bounds")
    if start_matrix.shape[0] == 0:
        raise InvariantViolation("at least one optimizer start is required")
    for index, start in enumerate(start_matrix):
        bounds.validate_point(start, label=f"optimizer start {index}")
    _validate_rate("stability_min", stability_min)
    if minimum_same_basin_starts is not None:
        if isinstance(minimum_same_basin_starts, bool) or not isinstance(
            minimum_same_basin_starts, int
        ):
            raise InvariantViolation("minimum_same_basin_starts must be an integer")
        if not 1 <= minimum_same_basin_starts <= start_matrix.shape[0]:
            raise InvariantViolation(
                "minimum_same_basin_starts must lie between one and the number of starts"
            )
    if not math.isfinite(basin_relative_tolerance) or basin_relative_tolerance < 0.0:
        raise InvariantViolation("basin_relative_tolerance must be finite and non-negative")
    if max_nfev <= 0:
        raise InvariantViolation("max_nfev must be positive")

    def residual(theta: FloatArray) -> FloatArray:
        prediction = _evaluate_model(function, theta, label="optimizer evaluation")
        if prediction.size != observed.size:
            raise InvariantViolation("model and observed moment dimensions differ")
        return (prediction - observed) / scales

    attempts: list[FitAttempt] = []
    for index, start in enumerate(start_matrix):
        result = least_squares(
            residual,
            start,
            bounds=(bounds.lower_array, bounds.upper_array),
            method="trf",
            max_nfev=max_nfev,
        )
        objective = float(np.dot(result.fun, result.fun))
        success = bool(result.success and np.isfinite(objective) and np.all(np.isfinite(result.x)))
        attempts.append(
            FitAttempt(
                start_index=index,
                start=tuple(float(value) for value in start),
                estimate=tuple(float(value) for value in result.x),
                objective=objective,
                success=success,
                status_code=int(result.status),
                message=str(result.message),
                evaluations=int(result.nfev),
                optimality=float(result.optimality),
            )
        )

    successful = [index for index, attempt in enumerate(attempts) if attempt.success]
    if successful:
        best_index = min(successful, key=lambda index: attempts[index].objective)
        best_objective = attempts[best_index].objective
        tolerance = basin_relative_tolerance * max(1.0, abs(best_objective))
        in_basin = sum(
            attempt.success and abs(attempt.objective - best_objective) <= tolerance
            for attempt in attempts
        )
        basin_fraction = in_basin / len(attempts)
    else:
        best_index = None
        in_basin = 0
        basin_fraction = 0.0

    stability_passed = (
        in_basin >= minimum_same_basin_starts
        if minimum_same_basin_starts is not None
        else basin_fraction >= stability_min
    )
    stability_threshold = (
        f">= {minimum_same_basin_starts} of {len(attempts)} starts"
        if minimum_same_basin_starts is not None
        else f">= {stability_min:g}"
    )

    criteria = (
        CriterionResult(
            name="successful_fit",
            status=GateStatus.PASS if best_index is not None else GateStatus.FAIL,
            value=len(successful),
            threshold=">= 1 successful finite fit",
        ),
        CriterionResult(
            name="same_objective_basin",
            status=GateStatus.PASS if stability_passed else GateStatus.FAIL,
            value=in_basin if minimum_same_basin_starts is not None else basin_fraction,
            threshold=stability_threshold,
        ),
    )
    gate = GateResult.from_criteria("multistart_recovery", criteria)
    return RecoveryResult(
        attempts=tuple(attempts),
        best_index=best_index,
        successful_starts=len(successful),
        same_basin_starts=in_basin,
        same_basin_fraction=basin_fraction,
        status=gate.status,
        gate=gate,
    )


@dataclass(frozen=True)
class ProfilePoint:
    parameter_value: float
    objective: float
    estimate: tuple[float, ...]
    success: bool
    successful_starts: int


@dataclass(frozen=True)
class ObjectiveProfile:
    parameter_index: int
    parameter_name: str
    points: tuple[ProfilePoint, ...]
    minimum_objective: float
    grid_minimum_objective: float
    status: GateStatus

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


def objective_profile(
    function: ModelFunction,
    observed_moments: ArrayLike,
    bounds: ParameterBounds,
    starts: ArrayLike,
    *,
    parameter_index: int,
    grid: ArrayLike,
    moment_scale: ArrayLike | None = None,
    max_nfev: int = 2_000,
    required_grid_points: int | None = None,
    require_full_range: bool = False,
) -> ObjectiveProfile:
    """Profile one parameter while re-optimizing all remaining parameters."""

    if not 0 <= parameter_index < bounds.dimension:
        raise InvariantViolation("profile parameter_index is out of range")
    grid_values = _as_1d_float("profile grid", grid)
    if grid_values.size == 0 or np.any(np.diff(grid_values) <= 0.0):
        raise InvariantViolation("profile grid must be non-empty, unique, and increasing")
    if required_grid_points is not None:
        if isinstance(required_grid_points, bool) or not isinstance(required_grid_points, int):
            raise InvariantViolation("required_grid_points must be an integer")
        if grid_values.size != required_grid_points:
            raise InvariantViolation(
                f"profile grid must contain exactly {required_grid_points} points"
            )
    if np.any(grid_values < bounds.lower[parameter_index]) or np.any(
        grid_values > bounds.upper[parameter_index]
    ):
        raise InvariantViolation("profile grid lies outside the parameter bound")
    if require_full_range and (
        not math.isclose(
            float(grid_values[0]), bounds.lower[parameter_index], rel_tol=0.0, abs_tol=1e-12
        )
        or not math.isclose(
            float(grid_values[-1]), bounds.upper[parameter_index], rel_tol=0.0, abs_tol=1e-12
        )
    ):
        raise InvariantViolation("profile grid must span the full parameter bound")
    observed = _as_1d_float("observed moments", observed_moments)
    scales = _validate_moment_scale(moment_scale, observed.size)
    start_matrix = _as_2d_float("profile starts", starts)
    if start_matrix.shape[1] != bounds.dimension or start_matrix.shape[0] == 0:
        raise InvariantViolation("profile starts must be a non-empty matrix matching bounds")
    for index, start in enumerate(start_matrix):
        bounds.validate_point(start, label=f"profile start {index}")

    unrestricted = recover_multistart(
        function,
        observed,
        bounds,
        start_matrix,
        moment_scale=scales,
        stability_min=0.0,
        max_nfev=max_nfev,
    )
    unrestricted_objective = (
        unrestricted.best.objective if unrestricted.best is not None else math.inf
    )

    free = np.asarray(
        [index for index in range(bounds.dimension) if index != parameter_index], dtype=int
    )
    points: list[ProfilePoint] = []
    for fixed_value in grid_values:
        candidates: list[tuple[float, FloatArray, bool]] = []
        if free.size == 0:
            estimate = np.asarray([fixed_value], dtype=float)
            prediction = _evaluate_model(function, estimate, label="profile evaluation")
            if prediction.size != observed.size:
                raise InvariantViolation("model and observed moment dimensions differ")
            residual = (prediction - observed) / scales
            objective = float(np.dot(residual, residual))
            candidates.append((objective, estimate, np.isfinite(objective)))
        else:
            lower_free = bounds.lower_array[free]
            upper_free = bounds.upper_array[free]

            def residual_free(free_values: FloatArray) -> FloatArray:
                estimate = np.empty(bounds.dimension, dtype=float)
                estimate[parameter_index] = fixed_value
                estimate[free] = free_values
                prediction = _evaluate_model(function, estimate, label="profile evaluation")
                if prediction.size != observed.size:
                    raise InvariantViolation("model and observed moment dimensions differ")
                return (prediction - observed) / scales

            for start in start_matrix:
                result = least_squares(
                    residual_free,
                    start[free],
                    bounds=(lower_free, upper_free),
                    method="trf",
                    max_nfev=max_nfev,
                )
                estimate = np.empty(bounds.dimension, dtype=float)
                estimate[parameter_index] = fixed_value
                estimate[free] = result.x
                objective = float(np.dot(result.fun, result.fun))
                success = bool(
                    result.success and np.isfinite(objective) and np.all(np.isfinite(estimate))
                )
                candidates.append((objective, estimate, success))

        valid = [candidate for candidate in candidates if candidate[2]]
        if valid:
            objective, estimate, _ = min(valid, key=lambda item: item[0])
            success = True
        else:
            objective = math.inf
            estimate = np.full(bounds.dimension, np.nan, dtype=float)
            estimate[parameter_index] = fixed_value
            success = False
        points.append(
            ProfilePoint(
                parameter_value=float(fixed_value),
                objective=float(objective),
                estimate=tuple(float(value) for value in estimate),
                success=success,
                successful_starts=len(valid),
            )
        )

    finite_objectives = [point.objective for point in points if point.success]
    grid_minimum = min(finite_objectives) if finite_objectives else math.inf
    status = (
        GateStatus.PASS
        if len(finite_objectives) == len(points) and math.isfinite(unrestricted_objective)
        else GateStatus.FAIL
    )
    return ObjectiveProfile(
        parameter_index=parameter_index,
        parameter_name=bounds.names[parameter_index],
        points=tuple(points),
        minimum_objective=unrestricted_objective,
        grid_minimum_objective=grid_minimum,
        status=status,
    )


@dataclass(frozen=True)
class ProfileSummary:
    accepted_points: int
    connected_components: int
    width: float
    width_fraction: float
    cutoff: float
    status: GateStatus
    gate: GateResult

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


def summarize_profile(
    profile: ObjectiveProfile,
    *,
    objective_difference_cutoff: float,
    parameter_range: float,
    maximum_width_fraction: float,
) -> ProfileSummary:
    """Summarize connectivity and width of a profile-objective acceptance set.

    The caller owns the statistical interpretation of the cutoff.  This function
    intentionally does not label an arbitrary quadratic-objective contour a
    confidence interval.
    """

    if not math.isfinite(objective_difference_cutoff) or objective_difference_cutoff < 0:
        raise InvariantViolation("objective_difference_cutoff must be finite and non-negative")
    if not math.isfinite(parameter_range) or parameter_range <= 0.0:
        raise InvariantViolation("parameter_range must be finite and positive")
    _validate_rate("maximum_width_fraction", maximum_width_fraction)
    if not math.isfinite(profile.minimum_objective):
        accepted = np.zeros(len(profile.points), dtype=bool)
    else:
        accepted = np.asarray(
            [
                point.success
                and point.objective - profile.minimum_objective <= objective_difference_cutoff
                for point in profile.points
            ],
            dtype=bool,
        )
    accepted_indices = np.flatnonzero(accepted)
    components = 0
    if accepted_indices.size:
        components = 1 + int(np.count_nonzero(np.diff(accepted_indices) > 1))
        grid = np.asarray([point.parameter_value for point in profile.points], dtype=float)
        first = int(accepted_indices[0])
        last = int(accepted_indices[-1])
        left_edge = float(grid[0]) if first == 0 else float((grid[first - 1] + grid[first]) / 2.0)
        right_edge = (
            float(grid[-1]) if last == grid.size - 1 else float((grid[last] + grid[last + 1]) / 2.0)
        )
        width = right_edge - left_edge
    else:
        width = math.inf
    width_fraction = width / parameter_range
    criteria = (
        CriterionResult(
            name="profile_connected",
            status=GateStatus.PASS if components == 1 else GateStatus.FAIL,
            value=components,
            threshold="exactly one connected accepted set",
        ),
        CriterionResult(
            name="profile_width",
            status=(
                GateStatus.PASS
                if math.isfinite(width_fraction) and width_fraction <= maximum_width_fraction
                else GateStatus.FAIL
            ),
            value=width_fraction,
            threshold=f"<= {maximum_width_fraction:g} of parameter range",
        ),
    )
    gate = GateResult.from_criteria("objective_profile", criteria)
    return ProfileSummary(
        accepted_points=int(accepted_indices.size),
        connected_components=components,
        width=width,
        width_fraction=width_fraction,
        cutoff=objective_difference_cutoff,
        status=gate.status,
        gate=gate,
    )


@dataclass(frozen=True)
class ClassificationSummary:
    evaluated_cases: int
    correct_cases: int
    accuracy: float
    per_block_evaluated: tuple[int, ...]
    per_block_correct: tuple[int, ...]
    per_block_accuracy: tuple[float, ...]
    status: GateStatus
    gate: GateResult

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


def classification_summary(
    truth: ArrayLike,
    estimates: ArrayLike,
    *,
    block_names: Sequence[str],
    minimum_accuracy: float,
    active_tolerance: float = 1e-12,
    zero_point: ArrayLike | None = None,
    parameter_ranges: ArrayLike | None = None,
    required_block_indices: Sequence[int] = (),
) -> ClassificationSummary:
    """Summarize dominant-block classification, allowing tied true blocks.

    Pairwise opposite-sign anchors have equal true magnitudes.  For those cases,
    an estimated dominant block is correct when it belongs to the tied true set.
    Per-block accuracy is computed only for cases with one unique true dominant.
    """

    true_matrix, estimate_matrix = _validate_paired_matrices(truth, estimates)
    names = _validate_names(block_names, true_matrix.shape[1], prefix="block")
    _validate_rate("minimum_accuracy", minimum_accuracy)
    if active_tolerance < 0.0 or not math.isfinite(active_tolerance):
        raise InvariantViolation("active_tolerance must be finite and non-negative")
    if zero_point is not None:
        zero = _as_1d_float("classification zero point", zero_point, true_matrix.shape[1])
        true_matrix = true_matrix - zero
        estimate_matrix = estimate_matrix - zero
    if parameter_ranges is not None:
        ranges = _as_1d_float(
            "classification parameter ranges", parameter_ranges, true_matrix.shape[1]
        )
        if np.any(ranges <= 0.0):
            raise InvariantViolation("classification parameter ranges must be positive")
        true_matrix = true_matrix / ranges
        estimate_matrix = estimate_matrix / ranges
    required = tuple(required_block_indices)
    if any(
        isinstance(index, bool)
        or not isinstance(index, int)
        or not 0 <= index < true_matrix.shape[1]
        for index in required
    ):
        raise InvariantViolation("required classification block index is out of range")
    if len(set(required)) != len(required):
        raise InvariantViolation("required classification block indices must be unique")

    evaluated = 0
    correct = 0
    per_evaluated = np.zeros(len(names), dtype=int)
    per_correct = np.zeros(len(names), dtype=int)
    for true_row, estimated_row in zip(true_matrix, estimate_matrix):
        largest = float(np.max(np.abs(true_row)))
        if largest <= active_tolerance:
            continue
        true_set = np.flatnonzero(
            np.isclose(np.abs(true_row), largest, rtol=0.0, atol=active_tolerance)
        )
        estimated_block = int(np.argmax(np.abs(estimated_row)))
        evaluated += 1
        is_correct = estimated_block in set(int(value) for value in true_set)
        correct += int(is_correct)
        if true_set.size == 1:
            block = int(true_set[0])
            per_evaluated[block] += 1
            per_correct[block] += int(is_correct)

    accuracy = correct / evaluated if evaluated else math.nan
    per_accuracy = tuple(
        (per_correct[index] / per_evaluated[index] if per_evaluated[index] else math.nan)
        for index in range(len(names))
    )
    passed = evaluated > 0 and accuracy >= minimum_accuracy
    criteria: tuple[CriterionResult, ...] = (
        CriterionResult(
            name="dominant_block_accuracy",
            status=GateStatus.PASS if passed else GateStatus.FAIL,
            value=accuracy,
            threshold=f">= {minimum_accuracy:g}",
            detail=f"{correct}/{evaluated} eligible cases",
        ),
    )
    criteria += tuple(
        CriterionResult(
            name=f"dominant_block_accuracy_{names[index]}",
            status=(
                GateStatus.PASS
                if per_evaluated[index] > 0 and per_accuracy[index] >= minimum_accuracy
                else GateStatus.FAIL
            ),
            value=per_accuracy[index],
            threshold=f">= {minimum_accuracy:g}",
            detail=f"{per_correct[index]}/{per_evaluated[index]} unique-dominant cases",
        )
        for index in required
    )
    gate = GateResult.from_criteria("shock_classification", criteria)
    return ClassificationSummary(
        evaluated_cases=evaluated,
        correct_cases=correct,
        accuracy=accuracy,
        per_block_evaluated=tuple(int(value) for value in per_evaluated),
        per_block_correct=tuple(int(value) for value in per_correct),
        per_block_accuracy=per_accuracy,
        status=gate.status,
        gate=gate,
    )


@dataclass(frozen=True)
class FalseAttributionSummary:
    eligible_cases: int
    false_positive_cases: int
    false_positive_rate: float
    focal_largest_cases: int
    focal_largest_rate: float
    status: GateStatus
    gate: GateResult

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


def false_attribution_summary(
    truth: ArrayLike,
    estimates: ArrayLike,
    interval_lower: ArrayLike,
    interval_upper: ArrayLike,
    *,
    focal_index: int,
    false_positive_max: float,
    focal_largest_max: float,
    zero_tolerance: float = 1e-12,
    eligible_mask: ArrayLike | None = None,
    estimate_activity_tolerance: float = 1e-10,
) -> FalseAttributionSummary:
    """Audit rival-only cases spuriously attributed to the focal shock.

    Omitted-mechanism DGPs have zero truth for *all* fitted blocks, so their
    eligibility cannot be inferred from a non-focal fitted coefficient.  Such
    callers must pass ``eligible_mask`` explicitly.  The legacy inferred rule
    remains available for simulated cases where a registered fitted rival block
    is genuinely active.
    """

    true_matrix, estimate_matrix = _validate_paired_matrices(truth, estimates)
    lower, upper = _validate_intervals(interval_lower, interval_upper, true_matrix.shape)
    if not 0 <= focal_index < true_matrix.shape[1]:
        raise InvariantViolation("focal_index is out of range")
    _validate_rate("false_positive_max", false_positive_max)
    _validate_rate("focal_largest_max", focal_largest_max)
    if zero_tolerance < 0.0 or not math.isfinite(zero_tolerance):
        raise InvariantViolation("zero_tolerance must be finite and non-negative")
    if estimate_activity_tolerance < 0.0 or not math.isfinite(estimate_activity_tolerance):
        raise InvariantViolation("estimate_activity_tolerance must be finite and non-negative")

    focal_zero = np.abs(true_matrix[:, focal_index]) <= zero_tolerance
    if eligible_mask is None:
        rival_columns = [index for index in range(true_matrix.shape[1]) if index != focal_index]
        if not rival_columns:
            raise InvariantViolation(
                "false-attribution inference requires a non-focal block or an eligible_mask"
            )
        rival_active = np.max(np.abs(true_matrix[:, rival_columns]), axis=1) > zero_tolerance
        eligible = focal_zero & rival_active
    else:
        supplied = np.asarray(eligible_mask)
        if supplied.ndim != 1 or supplied.size != true_matrix.shape[0]:
            raise InvariantViolation(
                "eligible_mask must be one-dimensional and match the number of cases"
            )
        if supplied.dtype.kind != "b":
            raise InvariantViolation("eligible_mask must contain booleans")
        eligible = focal_zero & supplied.astype(bool, copy=False)
    count = int(np.count_nonzero(eligible))
    false_positive = eligible & ((lower[:, focal_index] > 0.0) | (upper[:, focal_index] < 0.0))
    estimated_magnitudes = np.abs(estimate_matrix)
    largest_magnitude = np.max(estimated_magnitudes, axis=1)
    # Ties involving the focal block count conservatively as focal-largest;
    # an all-negligible estimate does not manufacture an active focal block.
    focal_largest = (
        eligible
        & (largest_magnitude > estimate_activity_tolerance)
        & np.isclose(
            estimated_magnitudes[:, focal_index],
            largest_magnitude,
            rtol=0.0,
            atol=estimate_activity_tolerance,
        )
    )
    false_count = int(np.count_nonzero(false_positive))
    largest_count = int(np.count_nonzero(focal_largest))
    false_rate = false_count / count if count else math.nan
    largest_rate = largest_count / count if count else math.nan
    criteria = (
        CriterionResult(
            name="null_false_positive",
            status=(
                GateStatus.PASS
                if count > 0 and false_rate <= false_positive_max
                else GateStatus.FAIL
            ),
            value=false_rate,
            threshold=f"<= {false_positive_max:g}",
            detail=f"{false_count}/{count} eligible rival-only cases",
        ),
        CriterionResult(
            name="focal_largest_under_rival_dgp",
            status=(
                GateStatus.PASS
                if count > 0 and largest_rate <= focal_largest_max
                else GateStatus.FAIL
            ),
            value=largest_rate,
            threshold=f"<= {focal_largest_max:g}",
            detail=f"{largest_count}/{count} eligible rival-only cases",
        ),
    )
    gate = GateResult.from_criteria("false_attribution", criteria)
    return FalseAttributionSummary(
        eligible_cases=count,
        false_positive_cases=false_count,
        false_positive_rate=false_rate,
        focal_largest_cases=largest_count,
        focal_largest_rate=largest_rate,
        status=gate.status,
        gate=gate,
    )


@dataclass(frozen=True)
class CoverageSummary:
    cases: int
    per_parameter_coverage: tuple[float, ...]
    overall_coverage: float
    status: GateStatus
    gate: GateResult

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


def coverage_summary(
    truth: ArrayLike,
    interval_lower: ArrayLike,
    interval_upper: ArrayLike,
    *,
    minimum: float,
    maximum: float,
    parameter_names: Sequence[str] | None = None,
    require_each: bool = True,
) -> CoverageSummary:
    """Report empirical interval coverage over repeated synthetic samples."""

    true_matrix = _as_2d_float("truth", truth)
    lower, upper = _validate_intervals(interval_lower, interval_upper, true_matrix.shape)
    _validate_rate("coverage minimum", minimum)
    _validate_rate("coverage maximum", maximum)
    if minimum > maximum:
        raise InvariantViolation("coverage minimum cannot exceed maximum")
    names = _validate_names(parameter_names, true_matrix.shape[1], prefix="parameter")
    covered = (lower <= true_matrix) & (true_matrix <= upper)
    per_parameter = np.mean(covered, axis=0)
    overall = float(np.mean(covered))
    parameter_criteria = tuple(
        CriterionResult(
            name=f"coverage_{name}",
            status=(GateStatus.PASS if minimum <= value <= maximum else GateStatus.FAIL),
            value=float(value),
            threshold=f"in [{minimum:g}, {maximum:g}]",
        )
        for name, value in zip(names, per_parameter)
    )
    overall_criterion = CriterionResult(
        name="coverage_overall",
        status=GateStatus.PASS if minimum <= overall <= maximum else GateStatus.FAIL,
        value=overall,
        threshold=f"in [{minimum:g}, {maximum:g}]",
    )
    criteria = parameter_criteria + (overall_criterion,) if require_each else (overall_criterion,)
    gate = GateResult.from_criteria("interval_coverage", criteria)
    return CoverageSummary(
        cases=true_matrix.shape[0],
        per_parameter_coverage=tuple(float(value) for value in per_parameter),
        overall_coverage=overall,
        status=gate.status,
        gate=gate,
    )


@dataclass(frozen=True)
class SignRecoverySummary:
    eligible_cases: int
    correct_cases: int
    accuracy: float
    status: GateStatus
    gate: GateResult

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS


def sign_recovery_summary(
    truth: ArrayLike,
    estimates: ArrayLike,
    *,
    focal_index: int,
    minimum_true_magnitude: float,
    minimum_accuracy: float,
) -> SignRecoverySummary:
    """Summarize focal-shock sign recovery above a declared truth magnitude."""

    true_matrix, estimate_matrix = _validate_paired_matrices(truth, estimates)
    if not 0 <= focal_index < true_matrix.shape[1]:
        raise InvariantViolation("focal_index is out of range")
    if minimum_true_magnitude < 0.0 or not math.isfinite(minimum_true_magnitude):
        raise InvariantViolation("minimum_true_magnitude must be finite and non-negative")
    _validate_rate("minimum_accuracy", minimum_accuracy)
    eligible = np.abs(true_matrix[:, focal_index]) >= minimum_true_magnitude
    correct = eligible & (
        np.sign(true_matrix[:, focal_index]) == np.sign(estimate_matrix[:, focal_index])
    )
    count = int(np.count_nonzero(eligible))
    correct_count = int(np.count_nonzero(correct))
    accuracy = correct_count / count if count else math.nan
    criterion = CriterionResult(
        name="focal_sign_recovery",
        status=(GateStatus.PASS if count > 0 and accuracy >= minimum_accuracy else GateStatus.FAIL),
        value=accuracy,
        threshold=f">= {minimum_accuracy:g}",
        detail=f"{correct_count}/{count} eligible cases",
    )
    gate = GateResult.from_criteria("sign_recovery", (criterion,))
    return SignRecoverySummary(
        eligible_cases=count,
        correct_cases=correct_count,
        accuracy=accuracy,
        status=gate.status,
        gate=gate,
    )


def _require_sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise InvariantViolation(f"{name} must be a JSON array")
    return value


def _json_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise InvariantViolation(f"{name} must be a JSON integer")
    return value


def _json_number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvariantViolation(f"{name} must be a JSON number")
    result = float(value)
    if not math.isfinite(result):
        raise InvariantViolation(f"{name} must be finite")
    return result


def _validate_rate(name: str, value: float) -> None:
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise InvariantViolation(f"{name} must be finite and in [0, 1]")


def _as_1d_float(name: str, values: ArrayLike, expected: int | None = None) -> FloatArray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1:
        raise InvariantViolation(f"{name} must be one-dimensional")
    if expected is not None and array.size != expected:
        raise InvariantViolation(f"{name} must have length {expected}, got {array.size}")
    if not np.all(np.isfinite(array)):
        raise InvariantViolation(f"{name} contains non-finite values")
    return array


def _as_2d_float(name: str, values: ArrayLike) -> FloatArray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2:
        raise InvariantViolation(f"{name} must be two-dimensional")
    if not np.all(np.isfinite(array)):
        raise InvariantViolation(f"{name} contains non-finite values")
    return array


def _evaluate_model(function: ModelFunction, theta: FloatArray, *, label: str) -> FloatArray:
    try:
        output = function(theta.copy())
    except InvariantViolation:
        raise
    except Exception as exc:
        raise InvariantViolation(f"model failed at {label}: {exc}") from exc
    return _as_1d_float(f"model output at {label}", output)


def _validate_moment_scale(moment_scale: ArrayLike | None, size: int) -> FloatArray:
    if moment_scale is None:
        return np.ones(size, dtype=float)
    scale = _as_1d_float("moment scale", moment_scale, expected=size)
    if np.any(scale <= 0.0):
        raise InvariantViolation("moment scale values must be strictly positive")
    return scale


def _validate_names(names: Sequence[str] | None, size: int, *, prefix: str) -> tuple[str, ...]:
    labels = (
        tuple(str(name) for name in names)
        if names is not None
        else tuple(f"{prefix}_{index}" for index in range(size))
    )
    if len(labels) != size:
        raise InvariantViolation(f"expected {size} {prefix} names, got {len(labels)}")
    if len(set(labels)) != len(labels) or any(not label for label in labels):
        raise InvariantViolation(f"{prefix} names must be non-empty and unique")
    return labels


def _validate_paired_matrices(
    truth: ArrayLike, estimates: ArrayLike
) -> tuple[FloatArray, FloatArray]:
    true_matrix = _as_2d_float("truth", truth)
    estimate_matrix = _as_2d_float("estimates", estimates)
    if true_matrix.shape != estimate_matrix.shape:
        raise InvariantViolation("truth and estimate matrices must have identical shapes")
    if true_matrix.shape[0] == 0 or true_matrix.shape[1] == 0:
        raise InvariantViolation("truth and estimate matrices cannot be empty")
    return true_matrix, estimate_matrix


def _validate_intervals(
    interval_lower: ArrayLike,
    interval_upper: ArrayLike,
    expected_shape: tuple[int, int],
) -> tuple[FloatArray, FloatArray]:
    lower = _as_2d_float("interval lower bounds", interval_lower)
    upper = _as_2d_float("interval upper bounds", interval_upper)
    if lower.shape != expected_shape or upper.shape != expected_shape:
        raise InvariantViolation(
            f"interval matrices must have shape {expected_shape}, got {lower.shape} and {upper.shape}"
        )
    if np.any(lower > upper):
        raise InvariantViolation("interval lower bounds cannot exceed upper bounds")
    return lower, upper
