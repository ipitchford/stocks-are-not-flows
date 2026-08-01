"""Manifest-ready fail-fast execution of the IDENT-0 design gate.

This runner intentionally cannot emit ``PASS-IDENT-0``.  It executes the
accounting, adapter, local-rank, mutation, and deterministic adversarial-profile
front of the gate.  If any blocking criterion fails, the preregistered expensive
Monte Carlo is unnecessary and every skipped criterion is recorded.  If this
front passes, the decision is ``CONTINUE-TO-FULL-GATE`` rather than a pass.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from .design import (
    build_full_preregistered_plan,
    denormalize_truth_cases,
    deterministic_starts,
    maximin_latin_hypercube,
    validate_neutral_maps_to_zero,
)
from .diagnostics import (
    Ident0Config,
    ParameterBounds,
    false_attribution_summary,
    jacobian_step_sweep,
    local_identification_summary,
    objective_profile,
    recover_multistart,
    summarize_profile,
)
from .errors import InvariantViolation
from .incidence import CompositeIncidenceReceipt, IncidenceLedger, build_signed_incidence_receipt
from .observation_adapter import PublicCoreObservationAdapter
from .response_model import (
    BLOCK_NAMES,
    NONMODELLED_PUBLIC_CORE_HOLDOUTS,
    PENDING_PUBLIC_CORE_TARGETS,
    TARGET_ROLE,
    LocalResponseModel,
)
from .rivals import exact_top_mimic, simulate_all_rivals


FloatArray = NDArray[np.float64]


FULL_GATE_UNRUN_CRITERIA: tuple[str, ...] = (
    "313-case noiseless recovery aggregation",
    "6,260 noisy-fit focal error aggregation",
    "z_top and z_middle 95% sign recovery",
    "synthetic Gaussian nominal-95% interval coverage in [0.90, 0.98]",
    "90% overall and separate top/middle shock classification",
    "64-case profile connectivity and width aggregation",
    "0.25-range rival-compensation tests",
    "95%-of-cases outer optimiser-stability aggregation",
    "wealth-channel-off structural mutation",
    "fixed-stock supply structural mutation",
    "landlord-tax-zero structural mutation",
    "owner/landlord output-label swap mutation",
    "P5 landlord-held-housing and net-yield signature",
)


@dataclass(frozen=True, slots=True)
class EvidenceCriterion:
    name: str
    status: str
    value: object
    threshold: str
    detail: str


@dataclass(frozen=True, slots=True)
class RivalCaseEvidence:
    dgp: str
    objective: float
    estimate: tuple[tuple[str, float], ...]
    largest_estimated_blocks: tuple[str, ...]
    same_basin_starts: int
    successful_starts: int
    profile_lower: float
    profile_upper: float
    profile_excludes_zero: bool
    profile_width_fraction: float
    profile_connected_components: int


@dataclass(frozen=True, slots=True)
class FailFastGateReport:
    schema_version: str
    decision: str
    pass_ident0_authorized: bool
    executed_scope: str
    model_variant: str
    seed: int
    target_observations: int
    diagnostic_observations: int
    public_core_absences: tuple[str, ...]
    nonmodelled_holdouts: tuple[str, ...]
    criteria: tuple[EvidenceCriterion, ...]
    local_rank_points_passing: int
    local_rank_points_total: int
    local_condition_numbers: tuple[tuple[float, ...], ...]
    rival_cases: tuple[RivalCaseEvidence, ...]
    full_plan_truth_cases: int
    full_plan_fits: int
    full_plan_optimizer_starts: int
    unrun_controlling_criteria: tuple[str, ...]
    assurance_boundary: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def bounds_from_config(config: Ident0Config) -> ParameterBounds:
    declared = dict(config.parameter_bounds)
    if tuple(declared) != BLOCK_NAMES:
        raise InvariantViolation(
            "parameter_bounds order must exactly match the response block order: "
            + ", ".join(BLOCK_NAMES)
        )
    return ParameterBounds(
        names=BLOCK_NAMES,
        lower=tuple(declared[name][0] for name in BLOCK_NAMES),
        upper=tuple(declared[name][1] for name in BLOCK_NAMES),
    )


def local_design_points(bounds: ParameterBounds, config: Ident0Config) -> FloatArray:
    """Build one selected midpoint plus 63 deterministic stratified points."""

    if config.local_rank_total_points < 2:
        raise InvariantViolation("local design requires a selected point and stratified points")
    stratified = maximin_latin_hypercube(
        config.local_rank_total_points - 1,
        bounds.dimension,
        seed=config.seed + 101,
        lower=0.10,
        upper=0.90,
        candidates=16,
    )
    normalized = np.vstack((np.full((1, bounds.dimension), 0.5, dtype=float), stratified))
    return bounds.lower_array + normalized * bounds.ranges


def run_fail_fast_gate(config: Ident0Config) -> FailFastGateReport:
    """Execute every decisive front-end criterion and return immutable evidence."""

    config.validate()
    bounds = bounds_from_config(config)
    validate_neutral_maps_to_zero(bounds)
    model = LocalResponseModel.baseline()
    adapter = PublicCoreObservationAdapter(config)
    model.verify_measurement_bridge()
    zero = np.zeros(bounds.dimension, dtype=float)
    adapted_zero = adapter.vector(model, zero, TARGET_ROLE)
    scales = adapter.scales_for(adapted_zero)

    def target_function(theta: FloatArray) -> FloatArray:
        return adapter.vector(model, theta, TARGET_ROLE).values

    criteria: list[EvidenceCriterion] = []
    schedule_passed = not PENDING_PUBLIC_CORE_TARGETS and len(adapted_zero.labels) == 57
    criteria.append(
        EvidenceCriterion(
            name="public_unit_observation_schedule",
            status="PASS" if schedule_passed else "FAIL",
            value={
                "target_count": len(adapted_zero.labels),
                "pending_targets": sorted(PENDING_PUBLIC_CORE_TARGETS),
                "H05_status": NONMODELLED_PUBLIC_CORE_HOLDOUTS["monthly_price_rent_index"].status,
            },
            threshold="57 frozen targets adapted; no pending target adapter; H05 explicit nonmodelled",
            detail="T07 remains pounds/week and tenure targets remain percentage levels.",
        )
    )

    full_plan = build_full_preregistered_plan(BLOCK_NAMES, seed=config.seed)
    physical_truth = denormalize_truth_cases(full_plan.cases, bounds)
    closure_fingerprints: list[str] = []
    closure_taxonomy: dict[str, int] = {}
    for case, truth in zip(full_plan.cases, physical_truth):
        receipt = build_signed_incidence_receipt(
            experiment_id=f"ident0-truth-{case.case_id}",
            year=config.years[-1],
            top_aggregate_delta=float(truth[0]),
            middle_aggregate_delta=float(truth[1]),
            top_recipient_mass=0.10,
            middle_recipient_mass=0.60,
        )
        closure_fingerprints.append(receipt.fingerprint())
        if isinstance(receipt, IncidenceLedger):
            closure_name = receipt.closure_class.value
        elif isinstance(receipt, CompositeIncidenceReceipt):
            closure_name = receipt.closure_id
        else:
            raise InvariantViolation("signed receipt builder returned an unknown receipt type")
        closure_taxonomy[closure_name] = closure_taxonomy.get(closure_name, 0) + 1
    expected_taxonomy = {
        "D1_RESOURCE_INJECTION": 6,
        "D1R_TOP_RESOURCE_WITHDRAWAL": 6,
        "D2_RESOURCE_LOSS": 6,
        "D2R_MIDDLE_RESOURCE_INJECTION": 6,
        "E0_REDISTRIBUTION": 1,
        "C0_COMPOSITE_OPEN": 257,
        "N0_NO_CHANGE": 31,
    }
    closure_passed = (
        len(closure_fingerprints) == full_plan.truth_cases
        and len(set(closure_fingerprints)) == full_plan.truth_cases
        and closure_taxonomy == expected_taxonomy
    )
    criteria.append(
        EvidenceCriterion(
            name="signed_closure_coverage",
            status="PASS" if closure_passed else "FAIL",
            value=closure_taxonomy,
            threshold=(
                f"all {full_plan.truth_cases} cases have unique valid receipts and the "
                "Amendment-02 elementary/composite taxonomy"
            ),
            detail="Receipts use D1/D1R/D2/D2R, direct E0, C0 composition, or N0 no-change.",
        )
    )

    points = local_design_points(bounds, config)
    local = local_identification_summary(
        target_function,
        points,
        bounds,
        config,
        moment_scale=scales,
        selected_point=0,
    )
    criteria.append(
        EvidenceCriterion(
            name="local_identification_64_point",
            status=local.status.value,
            value={
                "passing": local.points_passing,
                "total": local.points_total,
                "selected_passed": local.selected_point_passed,
            },
            threshold=(
                f">= {config.local_rank_required_points}/{config.local_rank_total_points}; "
                "selected midpoint passes"
            ),
            detail="Three scaled central-difference steps are used at every point.",
        )
    )

    exact = LocalResponseModel.known_negative_collinear()
    near = LocalResponseModel.known_negative_collinear(near=True, gap=1e-7)
    exact_adapter = PublicCoreObservationAdapter(config)
    near_adapter = PublicCoreObservationAdapter(config)
    exact_sweep = jacobian_step_sweep(
        lambda theta: exact_adapter.vector(exact, theta).values,
        zero,
        bounds,
        config,
        moment_scale=scales,
    )
    near_sweep = jacobian_step_sweep(
        lambda theta: near_adapter.vector(near, theta).values,
        zero,
        bounds,
        config,
        moment_scale=scales,
    )
    criteria.extend(
        (
            EvidenceCriterion(
                name="exact_collinearity_known_negative",
                status="PASS" if not exact_sweep.passed else "FAIL",
                value=tuple(item.rank for item in exact_sweep.svd),
                threshold="mutated top/middle collinearity must fail the rank gate",
                detail="A silent pass is a code-review blocker.",
            ),
            EvidenceCriterion(
                name="near_collinearity_known_negative",
                status="PASS" if not near_sweep.passed else "FAIL",
                value=tuple(item.condition_number for item in near_sweep.svd),
                threshold=f"condition number must exceed {config.condition_number_max:g}",
                detail="Algebraic rank alone cannot rescue an ill-conditioned design.",
            ),
        )
    )

    starts = deterministic_starts(
        bounds,
        config.starts_per_fit,
        seed=config.seed,
        maximin_candidates=16,
    )
    grid = np.linspace(bounds.lower_array[0], bounds.upper_array[0], config.profile_grid_points)
    rival_evidence: list[RivalCaseEvidence] = []
    estimates: list[tuple[float, ...]] = []
    interval_lower: list[tuple[float, ...]] = []
    interval_upper: list[tuple[float, ...]] = []
    all_rival_fits_stable = True
    for simulation in simulate_all_rivals(model):
        observed = adapter.vector_from_panel(model, simulation.panel, TARGET_ROLE).values
        recovery = recover_multistart(
            target_function,
            observed,
            bounds,
            starts,
            moment_scale=scales,
            stability_min=config.optimiser_stability_min,
            minimum_same_basin_starts=config.same_basin_starts_min,
        )
        if recovery.best is None:
            raise InvariantViolation(f"rival {simulation.dgp_name} produced no finite fit")
        all_rival_fits_stable = all_rival_fits_stable and recovery.passed
        estimate = tuple(recovery.best.estimate)
        profile = objective_profile(
            target_function,
            observed,
            bounds,
            starts,
            parameter_index=0,
            grid=grid,
            moment_scale=scales,
            required_grid_points=config.profile_grid_points,
            require_full_range=True,
        )
        summary = summarize_profile(
            profile,
            objective_difference_cutoff=config.profile_objective_difference_cutoff,
            parameter_range=bounds.ranges[0],
            maximum_width_fraction=config.profile_max_width_fraction,
        )
        lower, upper = _profile_acceptance_bounds(
            profile.points,
            profile.minimum_objective,
            config.profile_objective_difference_cutoff,
        )
        magnitudes = np.abs(np.asarray(estimate, dtype=float))
        maximum = float(np.max(magnitudes))
        largest = tuple(
            name
            for name, value in zip(BLOCK_NAMES, magnitudes)
            if maximum > 1e-10 and math.isclose(float(value), maximum, rel_tol=0.0, abs_tol=1e-10)
        )
        lower_row = bounds.lower_array.copy()
        upper_row = bounds.upper_array.copy()
        lower_row[0] = lower
        upper_row[0] = upper
        estimates.append(estimate)
        interval_lower.append(tuple(float(value) for value in lower_row))
        interval_upper.append(tuple(float(value) for value in upper_row))
        rival_evidence.append(
            RivalCaseEvidence(
                dgp=simulation.dgp_name,
                objective=recovery.best.objective,
                estimate=tuple(zip(BLOCK_NAMES, estimate)),
                largest_estimated_blocks=largest,
                same_basin_starts=recovery.same_basin_starts,
                successful_starts=recovery.successful_starts,
                profile_lower=lower,
                profile_upper=upper,
                profile_excludes_zero=lower > 0.0 or upper < 0.0,
                profile_width_fraction=summary.width_fraction,
                profile_connected_components=summary.connected_components,
            )
        )

    rival_truth = np.zeros((len(rival_evidence), bounds.dimension), dtype=float)
    false_attribution = false_attribution_summary(
        rival_truth,
        np.asarray(estimates, dtype=float),
        np.asarray(interval_lower, dtype=float),
        np.asarray(interval_upper, dtype=float),
        focal_index=0,
        false_positive_max=config.null_false_positive_max,
        focal_largest_max=config.rival_largest_block_max,
        eligible_mask=np.ones(len(rival_evidence), dtype=bool),
    )
    criteria.extend(
        (
            EvidenceCriterion(
                name="deterministic_rival_null_false_positive",
                status=(
                    "PASS"
                    if false_attribution.false_positive_rate <= config.null_false_positive_max
                    else "FAIL"
                ),
                value=false_attribution.false_positive_rate,
                threshold=f"<= {config.null_false_positive_max:g}",
                detail=(
                    f"{false_attribution.false_positive_cases}/"
                    f"{false_attribution.eligible_cases} profiles exclude zero"
                ),
            ),
            EvidenceCriterion(
                name="deterministic_rival_top_largest",
                status=(
                    "PASS"
                    if false_attribution.focal_largest_rate <= config.rival_largest_block_max
                    else "FAIL"
                ),
                value=false_attribution.focal_largest_rate,
                threshold=f"<= {config.rival_largest_block_max:g}",
                detail=(
                    f"{false_attribution.focal_largest_cases}/"
                    f"{false_attribution.eligible_cases} estimates make z_top co-largest"
                ),
            ),
            EvidenceCriterion(
                name="deterministic_rival_optimizer_stability",
                status="PASS" if all_rival_fits_stable else "FAIL",
                value=tuple(item.same_basin_starts for item in rival_evidence),
                threshold=(
                    f">= {config.same_basin_starts_min}/{config.starts_per_fit} starts "
                    "for every deterministic rival case"
                ),
                detail="The 95%-of-cases outer rule remains part of the unrun full gate.",
            ),
        )
    )

    mimic = exact_top_mimic(model).simulate(model, amplitude=0.65)
    mimic_observed = adapter.vector_from_panel(model, mimic.panel, TARGET_ROLE).values
    mimic_fit = recover_multistart(
        target_function,
        mimic_observed,
        bounds,
        starts,
        moment_scale=scales,
        minimum_same_basin_starts=config.same_basin_starts_min,
    )
    if mimic_fit.best is None:
        raise InvariantViolation("exact-top-mimic known negative produced no finite fit")
    mimic_profile = objective_profile(
        target_function,
        mimic_observed,
        bounds,
        starts,
        parameter_index=0,
        grid=grid,
        moment_scale=scales,
        required_grid_points=config.profile_grid_points,
        require_full_range=True,
    )
    mimic_lower, mimic_upper = _profile_acceptance_bounds(
        mimic_profile.points,
        mimic_profile.minimum_objective,
        config.profile_objective_difference_cutoff,
    )
    mimic_estimate = np.asarray(mimic_fit.best.estimate, dtype=float)
    mimic_detected = abs(mimic_estimate[0]) >= float(np.max(np.abs(mimic_estimate))) - 1e-10 and (
        mimic_lower > 0.0 or mimic_upper < 0.0
    )
    criteria.append(
        EvidenceCriterion(
            name="exact_top_mimic_known_negative",
            status="PASS" if mimic_detected else "FAIL",
            value={
                "estimated_z_top": float(mimic_estimate[0]),
                "profile": [mimic_lower, mimic_upper],
            },
            threshold="harness must expose false unique top attribution when labels are identical",
            detail="This is a harness detection control, not a rival the design could overcome.",
        )
    )

    # Amendment 01 requires these maps before a complete Gate D.  The local
    # coefficient harness does not implement them, so they are explicit
    # blockers rather than silent assumptions.
    criteria.extend(
        (
            EvidenceCriterion(
                name="owner_landlord_prices_to_aggregate_hpi_map",
                status="FAIL",
                value="NOT_IMPLEMENTED",
                threshold="executable observation map",
                detail="The response matrix emits aggregate HPI directly.",
            ),
            EvidenceCriterion(
                name="dwelling_stocks_to_household_tenure_map",
                status="FAIL",
                value="NOT_IMPLEMENTED",
                threshold="executable observation map",
                detail="The response matrix emits household tenure directly.",
            ),
            EvidenceCriterion(
                name="age_25_44_lifecycle_aggregation_map",
                status="FAIL",
                value="NOT_IMPLEMENTED",
                threshold="executable observation map",
                detail="The response matrix has no lifecycle state distribution.",
            ),
        )
    )

    failed = tuple(item.name for item in criteria if item.status != "PASS")
    decision = "FAIL-IDENT-0" if failed else "CONTINUE-TO-FULL-GATE"
    condition_numbers = tuple(
        tuple(item.condition_number for item in diagnostic.svd) for diagnostic in local.diagnostics
    )
    return FailFastGateReport(
        schema_version="0.2",
        decision=decision,
        pass_ident0_authorized=False,
        executed_scope="fail_fast_front_and_deterministic_adversarial_profiles",
        model_variant=model.variant,
        seed=config.seed,
        target_observations=len(model.observation_schedule(TARGET_ROLE)),
        diagnostic_observations=len(model.observation_schedule("prospectively_frozen_diagnostic")),
        public_core_absences=tuple(sorted(PENDING_PUBLIC_CORE_TARGETS)),
        nonmodelled_holdouts=tuple(
            sorted(
                item.preregistered_id or name
                for name, item in NONMODELLED_PUBLIC_CORE_HOLDOUTS.items()
            )
        ),
        criteria=tuple(criteria),
        local_rank_points_passing=local.points_passing,
        local_rank_points_total=local.points_total,
        local_condition_numbers=condition_numbers,
        rival_cases=tuple(rival_evidence),
        full_plan_truth_cases=full_plan.truth_cases,
        full_plan_fits=full_plan.total_fits,
        full_plan_optimizer_starts=full_plan.total_optimizer_starts,
        unrun_controlling_criteria=FULL_GATE_UNRUN_CRITERIA,
        assurance_boundary=(
            "The local response coefficients and wealth terminal loadings are design inputs, not empirical elasticities.",
            "The diagonal synthetic scales are a frozen recovery design, not administrative-data standard errors.",
            "A fail authorizes scenarios, identified sets, or near-zero bounds; it prohibits unique historical attribution.",
        ),
    )


def _profile_acceptance_bounds(
    points: Iterable[object],
    reference_objective: float,
    cutoff: float,
) -> tuple[float, float]:
    """Return conservative grid-cell bounds for an accepted objective contour."""

    frozen = tuple(points)
    if not frozen or not math.isfinite(reference_objective):
        raise InvariantViolation("profile acceptance requires finite evaluated points")
    grid = np.asarray([float(getattr(point, "parameter_value")) for point in frozen])
    accepted = np.asarray(
        [
            bool(getattr(point, "success"))
            and float(getattr(point, "objective")) - reference_objective <= cutoff
            for point in frozen
        ],
        dtype=bool,
    )
    indices = np.flatnonzero(accepted)
    if indices.size == 0:
        raise InvariantViolation("profile objective contour contains no accepted grid point")
    first = int(indices[0])
    last = int(indices[-1])
    lower = float(grid[0]) if first == 0 else float((grid[first - 1] + grid[first]) / 2.0)
    upper = float(grid[-1]) if last == grid.size - 1 else float((grid[last] + grid[last + 1]) / 2.0)
    return lower, upper


__all__ = [
    "EvidenceCriterion",
    "FailFastGateReport",
    "RivalCaseEvidence",
    "bounds_from_config",
    "local_design_points",
    "run_fail_fast_gate",
]
