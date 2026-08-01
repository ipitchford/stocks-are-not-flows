"""Executable local bridge from resource-flow amplitudes to a wealth-share stock.

IDENT-0 estimates signed amplitudes, but its permitted resource closures are
directional experiments.  This module therefore audits the positive top-flow
direction with ``D1_RESOURCE_INJECTION`` and the negative middle-flow direction
with ``D2_RESOURCE_LOSS``.  The response model uses the resulting tangent map
for signed local perturbations; it does not relabel an arbitrary joint shock as
a budget-neutral historical policy.

The bridge deliberately separates permanent model groups (``top`` and
``middle``) from round-specific observed ranks.  It evolves non-housing wealth
with the stock-flow identities in :mod:`measurement`, then differentiates the
registered Great Britain top-rank share at the no-shock baseline.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import NDArray

from .errors import InvariantViolation
from .incidence import (
    ClosureClass,
    UnitConvention,
    build_incidence_ledger,
)
from .measurement import (
    ObservedNonHousingWealth,
    RankWeight,
    WealthObservationMap,
    WealthPriceBasis,
    WealthStockFlow,
    evolve_non_housing_wealth,
    observe_non_housing_wealth,
    validate_incidence_wealth_bridge,
)


FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class LocalWealthBridgeConfig:
    """Frozen normalized units for the IDENT-0 wealth measurement tangent.

    Stocks and flows are normalized units, not pounds or empirical estimates.
    The terminal flow scales are chosen so the executable local derivative
    matches the transparent response design's terminal loadings of +1.70 and
    -0.35 percentage points.  Those loadings remain design values, not measured
    elasticities.
    """

    years: tuple[int, ...] = tuple(range(2008, 2020))
    top_population_mass: float = 0.10
    middle_population_mass: float = 0.60
    other_population_mass: float = 0.30
    opening_top_wealth: float = 55.0
    opening_middle_wealth: float = 35.0
    opening_other_wealth: float = 10.0
    top_type_top_rank_weight: float = 0.80
    middle_type_top_rank_weight: float = 0.02
    other_type_top_rank_weight: float = 0.02666666666666667
    target_top_terminal_sensitivity_pp: float = 1.70
    target_middle_terminal_sensitivity_pp: float = -0.35
    resource_pass_through: float = 1.0
    tolerance: float = 1e-10

    def __post_init__(self) -> None:
        if len(self.years) < 2 or any(
            right <= left for left, right in zip(self.years, self.years[1:])
        ):
            raise InvariantViolation("wealth-bridge years must be strictly increasing")
        numeric = (
            self.opening_top_wealth,
            self.opening_middle_wealth,
            self.opening_other_wealth,
            self.top_population_mass,
            self.middle_population_mass,
            self.other_population_mass,
            self.top_type_top_rank_weight,
            self.middle_type_top_rank_weight,
            self.other_type_top_rank_weight,
            self.target_top_terminal_sensitivity_pp,
            self.target_middle_terminal_sensitivity_pp,
            self.resource_pass_through,
            self.tolerance,
        )
        if any(not math.isfinite(value) for value in numeric):
            raise InvariantViolation("wealth-bridge configuration must be finite")
        if self.tolerance <= 0.0:
            raise InvariantViolation("wealth-bridge tolerance must be positive")
        if (
            min(
                self.opening_top_wealth,
                self.opening_middle_wealth,
                self.opening_other_wealth,
            )
            <= 0.0
        ):
            raise InvariantViolation("wealth-bridge opening stocks must be positive")
        masses = (
            self.top_population_mass,
            self.middle_population_mass,
            self.other_population_mass,
        )
        if any(value <= 0.0 for value in masses) or not math.isclose(
            sum(masses), 1.0, rel_tol=0.0, abs_tol=self.tolerance
        ):
            raise InvariantViolation(
                "wealth-bridge population masses must be positive and sum to one"
            )
        if not 0.0 <= self.top_type_top_rank_weight <= 1.0:
            raise InvariantViolation("top-type rank weight must lie in [0, 1]")
        if not 0.0 <= self.middle_type_top_rank_weight <= 1.0:
            raise InvariantViolation("middle-type rank weight must lie in [0, 1]")
        if not 0.0 <= self.other_type_top_rank_weight <= 1.0:
            raise InvariantViolation("other-type rank weight must lie in [0, 1]")
        if self.top_type_top_rank_weight <= self.middle_type_top_rank_weight:
            raise InvariantViolation("top types must load more heavily on the observed top rank")
        if self.target_top_terminal_sensitivity_pp <= 0.0:
            raise InvariantViolation("top terminal wealth sensitivity must be positive")
        if self.target_middle_terminal_sensitivity_pp >= 0.0:
            raise InvariantViolation("middle terminal wealth sensitivity must be negative")
        if not 0.0 <= self.resource_pass_through <= 1.0:
            raise InvariantViolation("wealth-bridge pass-through must lie in [0, 1]")
        if self.resource_pass_through <= 0.0:
            raise InvariantViolation("wealth-bridge pass-through must be strictly positive")
        top_rank_mass = (
            self.top_population_mass * self.top_type_top_rank_weight
            + self.middle_population_mass * self.middle_type_top_rank_weight
            + self.other_population_mass * self.other_type_top_rank_weight
        )
        if not math.isclose(top_rank_mass, 0.10, rel_tol=0.0, abs_tol=self.tolerance):
            raise InvariantViolation(
                "wealth-bridge observed top rank must contain exactly 10% of population mass"
            )


@dataclass(frozen=True, slots=True)
class DirectionAudit:
    """One permitted directional closure evolved through the wealth bridge."""

    closure_class: ClosureClass
    amplitude: float
    observations: tuple[ObservedNonHousingWealth, ...]
    flows: tuple[tuple[WealthStockFlow, WealthStockFlow, WealthStockFlow], ...]


class LocalWealthMeasurementBridge:
    """Generate and verify the local stock-share response to focal resource flows."""

    def __init__(self, config: LocalWealthBridgeConfig | None = None) -> None:
        self.config = LocalWealthBridgeConfig() if config is None else config
        if not isinstance(self.config, LocalWealthBridgeConfig):
            raise InvariantViolation("wealth bridge requires LocalWealthBridgeConfig")
        self.ramp = self._common_ramp()
        self.cumulative_ramp = np.cumsum(self.ramp)
        self.mapping = self._observation_map()
        self.opening_total = (
            self.config.opening_top_wealth
            + self.config.opening_middle_wealth
            + self.config.opening_other_wealth
        )
        self.opening_top_numerator = (
            self.config.top_type_top_rank_weight * self.config.opening_top_wealth
            + self.config.middle_type_top_rank_weight * self.config.opening_middle_wealth
            + self.config.other_type_top_rank_weight * self.config.opening_other_wealth
        )
        self.opening_top_share = self.opening_top_numerator / self.opening_total
        terminal_cumulative = float(self.cumulative_ramp[-1])
        if terminal_cumulative <= 0.0:
            raise InvariantViolation("wealth-bridge cumulative ramp must be positive")
        top_unit_derivative = self._share_derivative_per_flow_unit(
            self.config.top_type_top_rank_weight, terminal_cumulative
        )
        middle_unit_derivative = self._share_derivative_per_flow_unit(
            self.config.middle_type_top_rank_weight, terminal_cumulative
        )
        if top_unit_derivative <= 0.0 or middle_unit_derivative >= 0.0:
            raise InvariantViolation("wealth-bridge rank map has the wrong derivative signs")
        self.top_terminal_flow_scale = (
            self.config.target_top_terminal_sensitivity_pp / top_unit_derivative
        )
        self.middle_terminal_flow_scale = (
            self.config.target_middle_terminal_sensitivity_pp / middle_unit_derivative
        )
        if self.top_terminal_flow_scale <= 0.0 or self.middle_terminal_flow_scale <= 0.0:
            raise InvariantViolation("wealth-bridge resource scales must be positive")

    def _common_ramp(self) -> FloatArray:
        first = self.config.years[0]
        span = self.config.years[-1] - first
        ramp = np.asarray([(year - first) / span for year in self.config.years], dtype=float)
        ramp.setflags(write=False)
        return ramp

    def _observation_map(self) -> WealthObservationMap:
        top_weight = self.config.top_type_top_rank_weight
        middle_weight = self.config.middle_type_top_rank_weight
        other_weight = self.config.other_type_top_rank_weight
        return WealthObservationMap(
            mapping_id="ident0-gb-top-decile-local-bridge-v1",
            geography="Great Britain",
            top_rank="observed_top_decile",
            price_basis=WealthPriceBasis.CONSTANT_PRICE,
            rank_weights=(
                RankWeight("top", "observed_top_decile", top_weight, top_weight),
                RankWeight("top", "observed_other_90", 1.0 - top_weight, 1.0 - top_weight),
                RankWeight("middle", "observed_top_decile", middle_weight, middle_weight),
                RankWeight("middle", "observed_other_90", 1.0 - middle_weight, 1.0 - middle_weight),
                RankWeight("other", "observed_top_decile", other_weight, other_weight),
                RankWeight("other", "observed_other_90", 1.0 - other_weight, 1.0 - other_weight),
            ),
            tolerance=self.config.tolerance,
        )

    def _share_derivative_per_flow_unit(self, rank_weight: float, cumulative: float) -> float:
        """Percentage-point derivative for one terminal-flow normalized unit."""

        return (
            100.0
            * cumulative
            * self.config.resource_pass_through
            * (rank_weight - self.opening_top_share)
            / self.opening_total
        )

    def local_sensitivity_path(self) -> FloatArray:
        """Return year-by-(top,middle) top-share derivatives in percentage points."""

        top = np.asarray(
            [
                self.top_terminal_flow_scale
                * self._share_derivative_per_flow_unit(
                    self.config.top_type_top_rank_weight, float(cumulative)
                )
                for cumulative in self.cumulative_ramp
            ],
            dtype=float,
        )
        middle = np.asarray(
            [
                self.middle_terminal_flow_scale
                * self._share_derivative_per_flow_unit(
                    self.config.middle_type_top_rank_weight, float(cumulative)
                )
                for cumulative in self.cumulative_ramp
            ],
            dtype=float,
        )
        result = np.column_stack((top, middle))
        result.setflags(write=False)
        return result

    def sensitivity(self, year: int) -> tuple[float, float]:
        if year not in self.config.years:
            raise InvariantViolation(f"wealth-bridge year {year} is outside the core")
        row = self.local_sensitivity_path()[self.config.years.index(year)]
        return float(row[0]), float(row[1])

    def audit_direction(
        self,
        closure_class: ClosureClass,
        *,
        amplitude: float,
    ) -> DirectionAudit:
        """Evolve one Amendment-02 elementary direction through every stock identity."""

        if not math.isfinite(amplitude) or amplitude == 0.0:
            raise InvariantViolation("wealth-bridge audit amplitude must be finite and non-zero")
        if closure_class is ClosureClass.D1_RESOURCE_INJECTION and amplitude <= 0.0:
            raise InvariantViolation("D1 wealth audit requires a positive top amplitude")
        if closure_class is ClosureClass.D2_RESOURCE_LOSS and amplitude >= 0.0:
            raise InvariantViolation("D2 wealth audit requires a negative middle amplitude")
        if closure_class is ClosureClass.D1R_TOP_RESOURCE_WITHDRAWAL and amplitude >= 0.0:
            raise InvariantViolation("D1R wealth audit requires a negative top amplitude")
        if closure_class is ClosureClass.D2R_MIDDLE_RESOURCE_INJECTION and amplitude <= 0.0:
            raise InvariantViolation("D2R wealth audit requires a positive middle amplitude")
        if closure_class not in {
            ClosureClass.D1_RESOURCE_INJECTION,
            ClosureClass.D1R_TOP_RESOURCE_WITHDRAWAL,
            ClosureClass.D2_RESOURCE_LOSS,
            ClosureClass.D2R_MIDDLE_RESOURCE_INJECTION,
        }:
            raise InvariantViolation("local wealth tangent requires an elementary signed closure")

        opening = {
            "top": self.config.opening_top_wealth,
            "middle": self.config.opening_middle_wealth,
            "other": self.config.opening_other_wealth,
        }
        observations: list[ObservedNonHousingWealth] = []
        dated_flows: list[tuple[WealthStockFlow, WealthStockFlow, WealthStockFlow]] = []
        for year, ramp_value in zip(self.config.years, self.ramp):
            if closure_class in {
                ClosureClass.D1_RESOURCE_INJECTION,
                ClosureClass.D1R_TOP_RESOURCE_WITHDRAWAL,
            }:
                top_resource = amplitude * self.top_terminal_flow_scale * float(ramp_value)
                middle_resource = 0.0
            else:
                top_resource = 0.0
                middle_resource = amplitude * self.middle_terminal_flow_scale * float(ramp_value)

            top_flow = self._evolve("top", year, opening["top"], top_resource)
            middle_flow = self._evolve("middle", year, opening["middle"], middle_resource)
            other_flow = self._evolve("other", year, opening["other"], 0.0)
            flows = (top_flow, middle_flow, other_flow)
            if ramp_value > 0.0:
                aggregate_delta = top_resource + middle_resource
                ledger = build_incidence_ledger(
                    experiment_id=f"ident0-{closure_class.value.lower()}-{year}",
                    year=year,
                    closure_class=closure_class,
                    top_amount=top_resource,
                    top_unit=UnitConvention.AGGREGATE,
                    top_recipient_mass=0.10,
                    middle_amount=middle_resource,
                    middle_unit=UnitConvention.AGGREGATE,
                    middle_recipient_mass=0.60,
                    aggregate_resources_delta=aggregate_delta,
                    tolerance=self.config.tolerance,
                )
                validate_incidence_wealth_bridge(
                    ledger, (top_flow, middle_flow), tolerance=self.config.tolerance
                )
            observation = observe_non_housing_wealth(flows, self.mapping)
            observations.append(observation)
            dated_flows.append(flows)
            opening["top"] = top_flow.closing_constant_price_wealth
            opening["middle"] = middle_flow.closing_constant_price_wealth
            opening["other"] = other_flow.closing_constant_price_wealth

        return DirectionAudit(
            closure_class=closure_class,
            amplitude=float(amplitude),
            observations=tuple(observations),
            flows=tuple(dated_flows),
        )

    def _evolve(
        self, group: str, year: int, opening: float, latent_resource_flow: float
    ) -> WealthStockFlow:
        return evolve_non_housing_wealth(
            model_group=group,
            year=year,
            opening_non_housing_wealth=opening,
            latent_resource_flow=latent_resource_flow,
            resource_pass_through=self.config.resource_pass_through,
            other_active_accumulation=0.0,
            withdrawals=0.0,
            debt_change=0.0,
            realised_returns=0.0,
            non_housing_valuation_change=0.0,
            entry_exit=0.0,
            tolerance=self.config.tolerance,
        )

    def verify(self, *, audit_amplitude: float = 1e-5) -> None:
        """Raise unless executable D1/D2 paths reproduce the registered local tangent."""

        if not math.isfinite(audit_amplitude) or audit_amplitude <= 0.0:
            raise InvariantViolation("wealth-bridge audit amplitude must be positive")
        top_positive = self.audit_direction(
            ClosureClass.D1_RESOURCE_INJECTION, amplitude=audit_amplitude
        )
        top_negative = self.audit_direction(
            ClosureClass.D1R_TOP_RESOURCE_WITHDRAWAL, amplitude=-audit_amplitude
        )
        middle_negative = self.audit_direction(
            ClosureClass.D2_RESOURCE_LOSS, amplitude=-audit_amplitude
        )
        middle_positive = self.audit_direction(
            ClosureClass.D2R_MIDDLE_RESOURCE_INJECTION, amplitude=audit_amplitude
        )
        analytic = self.local_sensitivity_path()
        baseline = self.opening_top_share
        for index, year in enumerate(self.config.years):
            top_positive_numeric = (
                (top_positive.observations[index].closing_top_share - baseline)
                * 100.0
                / audit_amplitude
            )
            top_negative_numeric = (
                (top_negative.observations[index].closing_top_share - baseline)
                * 100.0
                / (-audit_amplitude)
            )
            middle_negative_numeric = (
                (middle_negative.observations[index].closing_top_share - baseline)
                * 100.0
                / (-audit_amplitude)
            )
            middle_positive_numeric = (
                (middle_positive.observations[index].closing_top_share - baseline)
                * 100.0
                / audit_amplitude
            )
            if not math.isclose(
                top_positive_numeric,
                float(analytic[index, 0]),
                rel_tol=2e-6,
                abs_tol=2e-8,
            ):
                raise InvariantViolation(
                    f"D1 executable wealth tangent disagrees in {year}: "
                    f"numeric={top_positive_numeric}, analytic={analytic[index, 0]}"
                )
            if not math.isclose(
                top_negative_numeric,
                float(analytic[index, 0]),
                rel_tol=2e-6,
                abs_tol=2e-8,
            ):
                raise InvariantViolation(
                    f"D1R executable wealth tangent disagrees in {year}: "
                    f"numeric={top_negative_numeric}, analytic={analytic[index, 0]}"
                )
            if not math.isclose(
                middle_negative_numeric,
                float(analytic[index, 1]),
                rel_tol=2e-6,
                abs_tol=2e-8,
            ):
                raise InvariantViolation(
                    f"D2 executable wealth tangent disagrees in {year}: "
                    f"numeric={middle_negative_numeric}, analytic={analytic[index, 1]}"
                )
            if not math.isclose(
                middle_positive_numeric,
                float(analytic[index, 1]),
                rel_tol=2e-6,
                abs_tol=2e-8,
            ):
                raise InvariantViolation(
                    f"D2R executable wealth tangent disagrees in {year}: "
                    f"numeric={middle_positive_numeric}, analytic={analytic[index, 1]}"
                )


__all__ = [
    "DirectionAudit",
    "LocalWealthBridgeConfig",
    "LocalWealthMeasurementBridge",
]
