"""Sharp conditional intervals with box-bounded nuisance coefficients."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.optimize import OptimizeResult, linprog

from .errors import InvariantViolation, SolverFailure
from .geometry import AssuranceScope


FloatArray = NDArray[np.float64]


class IntervalStatus(str, Enum):
    """Scientific status of the supplied conditional response set."""

    BOUNDED = "BOUNDED"
    UNBOUNDED = "UNBOUNDED"
    INFEASIBLE = "INFEASIBLE"


@dataclass(frozen=True)
class EndpointSolution:
    """One attained endpoint and its witness coefficients."""

    focal_coefficient: float
    nuisance_coefficients: tuple[float, ...]
    maximum_absolute_equality_residual: float
    maximum_bound_violation: float

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""

        return {
            "focal_coefficient": self.focal_coefficient,
            "nuisance_coefficients": list(self.nuisance_coefficients),
            "maximum_absolute_equality_residual": self.maximum_absolute_equality_residual,
            "maximum_bound_violation": self.maximum_bound_violation,
        }


@dataclass(frozen=True)
class FocalIntervalResult:
    """Sharp projection of a conditional linear response set onto the focal axis."""

    assurance_scope: AssuranceScope
    status: IntervalStatus
    focal_name: str
    nuisance_names: tuple[str, ...]
    n_moments: int
    lower: float | None
    upper: float | None
    width: float | None
    lower_solution: EndpointSolution | None
    upper_solution: EndpointSolution | None
    lower_solver_status: int
    upper_solver_status: int
    solver_messages: tuple[str, str]
    feasibility_tolerance: float
    empirical_england_bound: bool
    interpretation: str

    @property
    def feasible(self) -> bool:
        """Whether the supplied equality and box restrictions admit a solution."""

        return self.status is not IntervalStatus.INFEASIBLE

    @property
    def bounded(self) -> bool:
        """Whether both finite sharp endpoints were attained."""

        return self.status is IntervalStatus.BOUNDED

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation without infinities."""

        return {
            "assurance_scope": self.assurance_scope.value,
            "status": self.status.value,
            "focal_name": self.focal_name,
            "nuisance_names": list(self.nuisance_names),
            "n_moments": self.n_moments,
            "lower": self.lower,
            "upper": self.upper,
            "width": self.width,
            "lower_solution": (
                None if self.lower_solution is None else self.lower_solution.to_dict()
            ),
            "upper_solution": (
                None if self.upper_solution is None else self.upper_solution.to_dict()
            ),
            "lower_solver_status": self.lower_solver_status,
            "upper_solver_status": self.upper_solver_status,
            "solver_messages": list(self.solver_messages),
            "feasibility_tolerance": self.feasibility_tolerance,
            "empirical_england_bound": self.empirical_england_bound,
            "interpretation": self.interpretation,
        }


def sharp_focal_interval(
    response: ArrayLike,
    focal_column: ArrayLike,
    nuisance_columns: ArrayLike,
    nuisance_bounds: Sequence[tuple[float, float]],
    *,
    focal_bounds: tuple[float | None, float | None] = (None, None),
    focal_name: str = "focal",
    nuisance_names: Sequence[str] | None = None,
    feasibility_tolerance: float = 1e-8,
) -> FocalIntervalResult:
    """Solve the sharp focal interval conditional on supplied linear restrictions.

    The response set is

    ``{(beta, gamma): response = focal * beta + nuisance @ gamma,``
    ``                  gamma_lower <= gamma <= gamma_upper}``.

    Optional focal bounds may also be supplied.  Two deterministic HiGHS linear
    programs minimize and maximize ``beta``.  Because the feasible set is convex
    and the objective is linear, attained finite endpoints are sharp conditional
    on these supplied equalities and boxes.

    The result is deliberately labelled ``CONDITIONAL_RESPONSE_SET_ONLY`` and
    ``empirical_england_bound=False``.  Provenance and transport validation of
    response columns is outside this numerical routine.
    """

    observed = _finite_vector(response, "response")
    focal = _finite_vector(focal_column, "focal_column")
    nuisance = _finite_matrix(nuisance_columns, "nuisance_columns")
    if focal.size != observed.size:
        raise InvariantViolation(
            f"focal_column length must equal response length: {focal.size} != {observed.size}"
        )
    if nuisance.shape[0] != observed.size:
        raise InvariantViolation(
            "nuisance_columns row count must equal response length: "
            f"{nuisance.shape[0]} != {observed.size}"
        )
    focal_label = _nonempty_name(focal_name, "focal_name")
    names = _column_names(nuisance_names, nuisance.shape[1])
    boxes = _nuisance_boxes(nuisance_bounds, nuisance.shape[1])
    focal_box = _optional_box(focal_bounds, "focal_bounds")
    tolerance = _positive_finite(feasibility_tolerance, "feasibility_tolerance")

    design = np.column_stack((focal, nuisance))
    lower_objective = np.zeros(design.shape[1], dtype=float)
    lower_objective[0] = 1.0
    upper_objective = -lower_objective
    variable_bounds: list[tuple[float | None, float | None]] = [focal_box, *boxes]

    lower_result = linprog(
        lower_objective,
        A_eq=design,
        b_eq=observed,
        bounds=variable_bounds,
        method="highs",
    )
    upper_result = linprog(
        upper_objective,
        A_eq=design,
        b_eq=observed,
        bounds=variable_bounds,
        method="highs",
    )

    statuses = (int(lower_result.status), int(upper_result.status))
    messages = (str(lower_result.message), str(upper_result.message))
    if 2 in statuses:
        if statuses != (2, 2):
            raise SolverFailure(
                "endpoint programs disagreed on feasibility: "
                f"lower={statuses[0]}, upper={statuses[1]}"
            )
        return FocalIntervalResult(
            assurance_scope=AssuranceScope.CONDITIONAL_RESPONSE_SET_ONLY,
            status=IntervalStatus.INFEASIBLE,
            focal_name=focal_label,
            nuisance_names=names,
            n_moments=int(observed.size),
            lower=None,
            upper=None,
            width=None,
            lower_solution=None,
            upper_solution=None,
            lower_solver_status=statuses[0],
            upper_solver_status=statuses[1],
            solver_messages=messages,
            feasibility_tolerance=tolerance,
            empirical_england_bound=False,
            interpretation=(
                "The supplied equality and box restrictions have an empty response set; "
                "this is not an empirical England bound."
            ),
        )

    accepted_statuses = {0, 3}
    unexpected = [status for status in statuses if status not in accepted_statuses]
    if unexpected:
        raise SolverFailure(
            "HiGHS did not certify an optimum, infeasibility, or unboundedness: "
            f"statuses={statuses}, messages={messages}"
        )

    lower_solution = (
        _endpoint_solution(lower_result, design, observed, variable_bounds, tolerance)
        if statuses[0] == 0
        else None
    )
    upper_solution = (
        _endpoint_solution(upper_result, design, observed, variable_bounds, tolerance)
        if statuses[1] == 0
        else None
    )
    lower = None if lower_solution is None else lower_solution.focal_coefficient
    upper = None if upper_solution is None else upper_solution.focal_coefficient
    if lower is not None and upper is not None and lower > upper + tolerance:
        raise SolverFailure(f"computed lower endpoint exceeds upper endpoint: {lower} > {upper}")
    width = upper - lower if lower is not None and upper is not None else None
    status = IntervalStatus.BOUNDED if statuses == (0, 0) else IntervalStatus.UNBOUNDED
    interpretation = (
        "Finite endpoints are sharp conditional on the supplied equalities and boxes; "
        "provenance and transport remain unverified, so this is not an empirical England bound."
        if status is IntervalStatus.BOUNDED
        else (
            "At least one focal endpoint is unbounded conditional on the supplied equalities "
            "and boxes; this is not an empirical England bound."
        )
    )
    return FocalIntervalResult(
        assurance_scope=AssuranceScope.CONDITIONAL_RESPONSE_SET_ONLY,
        status=status,
        focal_name=focal_label,
        nuisance_names=names,
        n_moments=int(observed.size),
        lower=lower,
        upper=upper,
        width=width,
        lower_solution=lower_solution,
        upper_solution=upper_solution,
        lower_solver_status=statuses[0],
        upper_solver_status=statuses[1],
        solver_messages=messages,
        feasibility_tolerance=tolerance,
        empirical_england_bound=False,
        interpretation=interpretation,
    )


def _endpoint_solution(
    result: OptimizeResult,
    design: FloatArray,
    observed: FloatArray,
    bounds: Sequence[tuple[float | None, float | None]],
    tolerance: float,
) -> EndpointSolution:
    values = np.asarray(result.x, dtype=float)
    if values.ndim != 1 or values.size != design.shape[1] or not np.all(np.isfinite(values)):
        raise SolverFailure("HiGHS returned a malformed or non-finite endpoint witness")
    equality_residual = float(np.max(np.abs(design @ values - observed)))
    bound_violation = _maximum_bound_violation(values, bounds)
    if equality_residual > tolerance:
        raise SolverFailure(
            "endpoint witness exceeds the declared equality tolerance: "
            f"{equality_residual} > {tolerance}"
        )
    if bound_violation > tolerance:
        raise SolverFailure(
            f"endpoint witness exceeds the declared box tolerance: {bound_violation} > {tolerance}"
        )
    return EndpointSolution(
        focal_coefficient=float(values[0]),
        nuisance_coefficients=tuple(float(value) for value in values[1:]),
        maximum_absolute_equality_residual=equality_residual,
        maximum_bound_violation=bound_violation,
    )


def _maximum_bound_violation(
    values: FloatArray,
    bounds: Sequence[tuple[float | None, float | None]],
) -> float:
    maximum = 0.0
    for value, (lower, upper) in zip(values, bounds):
        if lower is not None:
            maximum = max(maximum, lower - float(value))
        if upper is not None:
            maximum = max(maximum, float(value) - upper)
    return max(maximum, 0.0)


def _nuisance_boxes(
    values: Sequence[tuple[float, float]],
    count: int,
) -> tuple[tuple[float, float], ...]:
    if isinstance(values, (str, bytes)):
        raise InvariantViolation("nuisance_bounds must be a sequence of finite pairs")
    try:
        supplied = tuple(values)
    except TypeError as exc:
        raise InvariantViolation("nuisance_bounds must be a sequence of finite pairs") from exc
    if len(supplied) != count:
        raise InvariantViolation(
            f"nuisance_bounds must contain one pair per nuisance column: {len(supplied)} != {count}"
        )
    result: list[tuple[float, float]] = []
    for index, pair in enumerate(supplied):
        if isinstance(pair, (str, bytes)):
            raise InvariantViolation(
                f"nuisance_bounds[{index}] must contain exactly [lower, upper]"
            )
        try:
            entries = tuple(pair)
        except TypeError as exc:
            raise InvariantViolation(f"nuisance_bounds[{index}] must be a numeric pair") from exc
        if len(entries) != 2:
            raise InvariantViolation(
                f"nuisance_bounds[{index}] must contain exactly [lower, upper]"
            )
        lower = _finite_bound(entries[0], f"nuisance_bounds[{index}] lower")
        upper = _finite_bound(entries[1], f"nuisance_bounds[{index}] upper")
        if lower > upper:
            raise InvariantViolation(f"nuisance_bounds[{index}] lower exceeds upper")
        result.append((lower, upper))
    return tuple(result)


def _optional_box(
    values: tuple[float | None, float | None],
    field: str,
) -> tuple[float | None, float | None]:
    if isinstance(values, (str, bytes)):
        raise InvariantViolation(f"{field} must be a numeric-or-null pair")
    try:
        entries = tuple(values)
    except TypeError as exc:
        raise InvariantViolation(f"{field} must be a numeric-or-null pair") from exc
    if len(entries) != 2:
        raise InvariantViolation(f"{field} must contain exactly [lower, upper]")
    lower = None if entries[0] is None else _finite_bound(entries[0], f"{field} lower")
    upper = None if entries[1] is None else _finite_bound(entries[1], f"{field} upper")
    if lower is not None and upper is not None and lower > upper:
        raise InvariantViolation(f"{field} lower exceeds upper")
    return lower, upper


def _finite_bound(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise InvariantViolation(f"{field} must be finite and numeric")
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise InvariantViolation(f"{field} must be finite and numeric") from exc
    if not math.isfinite(converted):
        raise InvariantViolation(f"{field} must be finite and numeric")
    return converted


def _positive_finite(value: float, field: str) -> float:
    if isinstance(value, bool):
        raise InvariantViolation(f"{field} must be finite and positive")
    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise InvariantViolation(f"{field} must be finite and positive") from exc
    if not math.isfinite(converted) or converted <= 0.0:
        raise InvariantViolation(f"{field} must be finite and positive")
    return converted


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
