"""Deterministic experimental designs for IDENT-0.

The full preregistered design contains 313 truth cases and 6,573 fits, but this
module only *describes* that workload.  Unit tests and local smoke runs use the
small design builder; nothing launches thousands of optimizations implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Sequence

import numpy as np
from numpy.typing import NDArray

from .diagnostics import ParameterBounds
from .errors import InvariantViolation


FloatArray = NDArray[np.float64]

DEFAULT_SHOCK_BLOCKS = (
    "z_top",
    "z_middle",
    "credit",
    "planning_supply",
    "landlord_tax",
    "rate",
    "demographics",
)


@dataclass(frozen=True)
class TruthCase:
    """One normalized known-truth parameter vector."""

    case_id: str
    kind: str
    values: tuple[float, ...]
    active_blocks: tuple[str, ...]

    def as_array(self) -> FloatArray:
        return np.asarray(self.values, dtype=float)


@dataclass(frozen=True)
class DesignPlan:
    """Declarative Monte Carlo workload; construction does not execute fits."""

    block_names: tuple[str, ...]
    cases: tuple[TruthCase, ...]
    noisy_replications_per_case: int
    starts_per_fit: int
    seed: int
    label: str

    @property
    def truth_cases(self) -> int:
        return len(self.cases)

    @property
    def noise_free_fits(self) -> int:
        return self.truth_cases

    @property
    def noisy_fits(self) -> int:
        return self.truth_cases * self.noisy_replications_per_case

    @property
    def total_fits(self) -> int:
        return self.noise_free_fits + self.noisy_fits

    @property
    def total_optimizer_starts(self) -> int:
        return self.total_fits * self.starts_per_fit

    def kind_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in self.cases:
            counts[case.kind] = counts.get(case.kind, 0) + 1
        return counts

    def matrix(self) -> FloatArray:
        if not self.cases:
            return np.empty((0, len(self.block_names)), dtype=float)
        return np.asarray([case.values for case in self.cases], dtype=float)


def maximin_latin_hypercube(
    n_points: int,
    n_dimensions: int,
    *,
    seed: int,
    lower: float = 0.1,
    upper: float = 0.9,
    candidates: int = 16,
) -> FloatArray:
    """Return a deterministic, candidate-selected Latin hypercube.

    Each candidate is a randomized Latin hypercube generated from one seeded
    stream.  The candidate maximizing the minimum pairwise Euclidean distance is
    retained.  This is a lightweight maximin approximation, not an optimizer over
    all Latin hypercubes.
    """

    if isinstance(n_points, bool) or n_points <= 0:
        raise InvariantViolation("n_points must be a positive integer")
    if isinstance(n_dimensions, bool) or n_dimensions <= 0:
        raise InvariantViolation("n_dimensions must be a positive integer")
    if isinstance(candidates, bool) or candidates <= 0:
        raise InvariantViolation("candidates must be a positive integer")
    if seed < 0:
        raise InvariantViolation("seed must be non-negative")
    if not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower:
        raise InvariantViolation("Latin-hypercube bounds must be finite and increasing")

    rng = np.random.default_rng(seed)
    best: FloatArray | None = None
    best_score = -math.inf
    for _ in range(candidates):
        unit = np.empty((n_points, n_dimensions), dtype=float)
        for dimension in range(n_dimensions):
            permutation = rng.permutation(n_points)
            jitter = rng.random(n_points)
            unit[:, dimension] = (permutation + jitter) / n_points
        design = lower + (upper - lower) * unit
        score = _minimum_pairwise_distance(design)
        if score > best_score:
            best_score = score
            best = design.copy()

    if best is None:
        raise InvariantViolation("Latin-hypercube generation produced no candidate")
    return best


def build_truth_cases(
    block_names: Sequence[str] = DEFAULT_SHOCK_BLOCKS,
    *,
    seed: int = 20260801,
    lhs_points: int = 256,
    lhs_lower: float = 0.1,
    lhs_upper: float = 0.9,
    neutral: float = 0.5,
    negative: float = 0.25,
    positive: float = 0.75,
    maximin_candidates: int = 16,
) -> tuple[TruthCase, ...]:
    """Build Latin-hypercube, zero, one-at-a-time, and pairwise anchors.

    Values are in normalized parameter-range units.  ``neutral`` denotes the
    physical zero-shock value after the caller's affine bounds transformation;
    callers with asymmetric physical bounds must verify that mapping explicitly.
    """

    names = _validate_block_names(block_names)
    _validate_anchor_values(
        lhs_lower=lhs_lower,
        lhs_upper=lhs_upper,
        neutral=neutral,
        negative=negative,
        positive=positive,
    )
    lhs = maximin_latin_hypercube(
        lhs_points,
        len(names),
        seed=seed,
        lower=lhs_lower,
        upper=lhs_upper,
        candidates=maximin_candidates,
    )

    cases: list[TruthCase] = []
    for index, row in enumerate(lhs):
        active = tuple(
            name
            for name, value in zip(names, row)
            if not math.isclose(float(value), neutral, rel_tol=0.0, abs_tol=1e-12)
        )
        cases.append(
            TruthCase(
                case_id=f"lhs_{index:03d}",
                kind="latin_hypercube",
                values=tuple(float(value) for value in row),
                active_blocks=active,
            )
        )

    center = np.full(len(names), neutral, dtype=float)
    cases.append(
        TruthCase(
            case_id="anchor_zero",
            kind="zero_anchor",
            values=tuple(float(value) for value in center),
            active_blocks=(),
        )
    )
    for block_index, name in enumerate(names):
        for direction, value in (("negative", negative), ("positive", positive)):
            row = center.copy()
            row[block_index] = value
            cases.append(
                TruthCase(
                    case_id=f"anchor_{_safe_id(name)}_{direction}",
                    kind="one_at_a_time_anchor",
                    values=tuple(float(item) for item in row),
                    active_blocks=(name,),
                )
            )

    for left, right in combinations(range(len(names)), 2):
        for left_value, right_value, label in (
            (positive, negative, "positive_negative"),
            (negative, positive, "negative_positive"),
        ):
            row = center.copy()
            row[left] = left_value
            row[right] = right_value
            cases.append(
                TruthCase(
                    case_id=(f"pair_{_safe_id(names[left])}_{_safe_id(names[right])}_{label}"),
                    kind="pairwise_confounding_anchor",
                    values=tuple(float(item) for item in row),
                    active_blocks=(names[left], names[right]),
                )
            )

    identifiers = [case.case_id for case in cases]
    if len(identifiers) != len(set(identifiers)):
        raise InvariantViolation("truth-case identifiers are not unique")
    return tuple(cases)


def build_full_preregistered_plan(
    block_names: Sequence[str] = DEFAULT_SHOCK_BLOCKS,
    *,
    seed: int = 20260801,
) -> DesignPlan:
    """Expose the full 313-case / 6,573-fit plan without executing it."""

    names = _validate_block_names(block_names)
    if len(names) != 7:
        raise InvariantViolation(
            "the frozen full plan requires exactly seven shock blocks to produce 313 cases"
        )
    cases = build_truth_cases(names, seed=seed, lhs_points=256)
    plan = DesignPlan(
        block_names=names,
        cases=cases,
        noisy_replications_per_case=20,
        starts_per_fit=32,
        seed=seed,
        label="full_preregistered_313_case_plan",
    )
    if plan.truth_cases != 313 or plan.total_fits != 6573:
        raise InvariantViolation(
            f"full design count drift: {plan.truth_cases} cases and {plan.total_fits} fits"
        )
    return plan


def build_smoke_plan(
    block_names: Sequence[str] = DEFAULT_SHOCK_BLOCKS,
    *,
    seed: int = 20260801,
    lhs_points: int = 4,
    noisy_replications_per_case: int = 1,
    starts_per_fit: int = 3,
) -> DesignPlan:
    """Small deterministic design for unit/integration tests and local debugging."""

    names = _validate_block_names(block_names)
    if lhs_points <= 0:
        raise InvariantViolation("lhs_points must be positive")
    if noisy_replications_per_case < 0:
        raise InvariantViolation("noisy_replications_per_case cannot be negative")
    if starts_per_fit <= 0:
        raise InvariantViolation("starts_per_fit must be positive")
    cases = build_truth_cases(
        names,
        seed=seed,
        lhs_points=lhs_points,
        maximin_candidates=4,
    )
    return DesignPlan(
        block_names=names,
        cases=cases,
        noisy_replications_per_case=noisy_replications_per_case,
        starts_per_fit=starts_per_fit,
        seed=seed,
        label="smoke_plan",
    )


def deterministic_starts(
    bounds: ParameterBounds,
    n_starts: int,
    *,
    seed: int,
    normalized_lower: float = 0.05,
    normalized_upper: float = 0.95,
    include_midpoint: bool = True,
    maximin_candidates: int = 16,
) -> FloatArray:
    """Generate deterministic space-filling bounded optimizer starts."""

    if n_starts <= 0:
        raise InvariantViolation("n_starts must be positive")
    if include_midpoint and n_starts == 1:
        normalized = np.full((1, bounds.dimension), 0.5, dtype=float)
    else:
        lhs_count = n_starts - int(include_midpoint)
        lhs = maximin_latin_hypercube(
            lhs_count,
            bounds.dimension,
            seed=seed,
            lower=normalized_lower,
            upper=normalized_upper,
            candidates=maximin_candidates,
        )
        if include_midpoint:
            normalized = np.vstack((np.full((1, bounds.dimension), 0.5), lhs))
        else:
            normalized = lhs
    return bounds.lower_array + normalized * bounds.ranges


def denormalize_truth_cases(cases: Sequence[TruthCase], bounds: ParameterBounds) -> FloatArray:
    """Convert normalized truth cases to the declared physical parameter box."""

    if not cases:
        raise InvariantViolation("at least one truth case is required")
    matrix = np.asarray([case.values for case in cases], dtype=float)
    if matrix.ndim != 2 or matrix.shape[1] != bounds.dimension:
        raise InvariantViolation("truth-case dimension does not match parameter bounds")
    if not np.all(np.isfinite(matrix)) or np.any(matrix < 0.0) or np.any(matrix > 1.0):
        raise InvariantViolation("normalized truth cases must be finite and lie in [0, 1]")
    return bounds.lower_array + matrix * bounds.ranges


def validate_neutral_maps_to_zero(
    bounds: ParameterBounds,
    *,
    neutral: float = 0.5,
    tolerance: float = 1e-12,
) -> None:
    """Raise unless the normalized neutral design coordinate is physical zero."""

    if not math.isfinite(neutral) or not 0.0 <= neutral <= 1.0:
        raise InvariantViolation("neutral design coordinate must lie in [0, 1]")
    if not math.isfinite(tolerance) or tolerance <= 0.0:
        raise InvariantViolation("neutral-mapping tolerance must be finite and positive")
    mapped = bounds.lower_array + neutral * bounds.ranges
    if np.any(np.abs(mapped) > tolerance):
        details = ", ".join(f"{name}={value:.6g}" for name, value in zip(bounds.names, mapped))
        raise InvariantViolation(
            "normalized neutral coordinate does not map to physical zero: " + details
        )


def _minimum_pairwise_distance(points: FloatArray) -> float:
    if points.shape[0] == 1:
        return math.inf
    best = math.inf
    for left in range(points.shape[0] - 1):
        differences = points[left + 1 :] - points[left]
        distances = np.sqrt(np.sum(differences * differences, axis=1))
        candidate = float(np.min(distances))
        if candidate < best:
            best = candidate
    return best


def _validate_block_names(block_names: Sequence[str]) -> tuple[str, ...]:
    names = tuple(str(name) for name in block_names)
    if not names:
        raise InvariantViolation("at least one shock block is required")
    if any(not name for name in names) or len(names) != len(set(names)):
        raise InvariantViolation("shock-block names must be non-empty and unique")
    return names


def _validate_anchor_values(
    *,
    lhs_lower: float,
    lhs_upper: float,
    neutral: float,
    negative: float,
    positive: float,
) -> None:
    values = (lhs_lower, lhs_upper, neutral, negative, positive)
    if not all(math.isfinite(value) for value in values):
        raise InvariantViolation("truth-design levels must be finite")
    if not 0.0 <= lhs_lower < lhs_upper <= 1.0:
        raise InvariantViolation("LHS bounds must satisfy 0 <= lower < upper <= 1")
    if not 0.0 <= negative < neutral < positive <= 1.0:
        raise InvariantViolation(
            "anchor levels must satisfy 0 <= negative < neutral < positive <= 1"
        )
    if negative < lhs_lower or positive > lhs_upper:
        raise InvariantViolation("anchor levels must lie inside the LHS design interval")


def _safe_id(name: str) -> str:
    safe = "".join(character if character.isalnum() else "_" for character in name)
    return safe.strip("_") or "block"
