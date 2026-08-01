"""Transparent annual local-response model for the IDENT-0 design gate.

This module is deliberately *not* a housing equilibrium model.  It is a small,
auditable map from seven scalar shock amplitudes to the locally modelled subset
of the public-core 2008--2019 schedule.  Every shock uses the same linear ramp,
so distinguishability comes from response and measurement geometry rather than
from visually different shock dates.

All reported values are deviations from a separately calibrated baseline.  A
zero therefore means a modelled zero deviation.  By contrast, gross tenure
flows and landlord identity are unavailable, and several registered holdouts do
not have a defensible direct map into this prototype.  They live in explicit
absent/non-modelled registries; APIs return ``None`` or raise instead of
manufacturing zeros or proxies.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray

from .errors import InvariantViolation
from .measurement_bridge import LocalWealthMeasurementBridge


YEARS: tuple[int, ...] = tuple(range(2008, 2020))

# Canonical parameter ordering follows the seven blocks frozen in the pilot
# preregistration.  Positive ``planning_supply`` means greater primitive
# capacity/productivity; a planning restriction therefore has negative sign.
BLOCK_NAMES: tuple[str, ...] = (
    "z_top",
    "z_middle",
    "credit",
    "planning_supply",
    "landlord_tax",
    "rate",
    "demographics",
)

BLOCK_ALIASES = MappingProxyType(
    {
        "top_resources": "z_top",
        "middle_resources": "z_middle",
        "supply": "planning_supply",
        "tax": "landlord_tax",
        "interest_rate": "rate",
    }
)

TARGET_ROLE = "target"
DIAGNOSTIC_ROLE = "prospectively_frozen_diagnostic"
VALID_ROLES = frozenset((TARGET_ROLE, DIAGNOSTIC_ROLE))
VALID_ADAPTERS = frozenset(
    (
        "identity_deviation",
        "owner_share_level",
        "private_renter_share_level",
        "nominal_rent_level_from_log_pct",
    )
)


@dataclass(frozen=True, slots=True)
class ObservationSpec:
    """One dated entry in the locally modelled public-core observation vector.

    ``period`` preserves survey/financial-year labels.  ``anchor_year`` is only
    the annual state at which the local-response prototype evaluates that
    period; it must not be reinterpreted as an exact survey date.
    """

    observation_id: str
    moment: str
    anchor_year: int
    period: str
    role: str
    geography: str
    unit: str
    adapter: str = "identity_deviation"

    def __post_init__(self) -> None:
        if not self.observation_id:
            raise InvariantViolation("observation_id must be non-empty")
        if self.anchor_year not in YEARS:
            raise InvariantViolation(
                f"anchor_year {self.anchor_year} is outside the 2008--2019 core"
            )
        if self.role not in VALID_ROLES:
            raise InvariantViolation(f"unknown observation role: {self.role!r}")
        if not self.period or not self.geography or not self.unit:
            raise InvariantViolation(f"observation {self.observation_id!r} has incomplete metadata")
        if self.adapter not in VALID_ADAPTERS:
            raise InvariantViolation(
                f"observation {self.observation_id!r} has unknown adapter {self.adapter!r}"
            )


@dataclass(frozen=True, slots=True)
class AbsentMeasurement:
    """Metadata for an unavailable or deliberately non-modelled response object."""

    moment: str
    reason: str
    status: str = "absent_public_core"
    preregistered_id: str | None = None

    def __post_init__(self) -> None:
        if not self.moment or not self.reason:
            raise InvariantViolation("absent measurements require a name and reason")
        if self.status not in {
            "absent_public_core",
            "nonmodelled_holdout",
            "pending_target_adapter",
        }:
            raise InvariantViolation(f"unknown unavailable-measurement status: {self.status!r}")
        if self.status in {"nonmodelled_holdout", "pending_target_adapter"} and not (
            self.preregistered_id
        ):
            raise InvariantViolation(
                "a non-modelled registered object requires its preregistered ID"
            )


ABSENT_PUBLIC_CORE_MEASUREMENTS = MappingProxyType(
    {
        item.moment: item
        for item in (
            AbsentMeasurement(
                "gross_owner_to_landlord_flow",
                "public data do not label owner-to-let dwelling conversions",
            ),
            AbsentMeasurement(
                "gross_landlord_to_owner_flow",
                "public data do not label let-to-owner dwelling conversions",
            ),
            AbsentMeasurement(
                "household_landlord_identity",
                "public transaction and stock series do not identify household landlords",
            ),
            AbsentMeasurement(
                "institutional_landlord_identity",
                "the unrestricted public core does not provide a complete owner-identity split",
            ),
        )
    }
)


PENDING_PUBLIC_CORE_TARGETS: Mapping[str, AbsentMeasurement] = MappingProxyType({})


NONMODELLED_PUBLIC_CORE_HOLDOUTS = MappingProxyType(
    {
        item.moment: item
        for item in (
            AbsentMeasurement(
                "all_age_tenure_share_pp",
                "H02 has no direct age-aggregation map in the local response prototype",
                "nonmodelled_holdout",
                "H02_TENURE_ALLAGE",
            ),
            AbsentMeasurement(
                "rent_burden_pct",
                "H03 requires joint rent and current-income distributions, not aggregate rent",
                "nonmodelled_holdout",
                "H03_RENT_BURDEN",
            ),
            AbsentMeasurement(
                "property_wealth_distribution",
                "H04 is a revaluation falsification and property wealth is excluded from z_top",
                "nonmodelled_holdout",
                "H04_PROPERTY_WEALTH",
            ),
            AbsentMeasurement(
                "monthly_price_rent_index",
                (
                    "H05 is a 60-month Jan-2015--Dec-2019 diagnostic; the annual prototype "
                    "has no preregistered interpolation operator or monthly covariance"
                ),
                "nonmodelled_holdout",
                "H05_PRICE_RENT_INDEX",
            ),
            AbsentMeasurement(
                "mlar_btl_lending",
                "H07 lending stocks and advances do not map to the quoted BTL-owner spread",
                "nonmodelled_holdout",
                "H07_MLAR_BTL",
            ),
            AbsentMeasurement(
                "ftb_borrower_profile",
                "H08 borrower distributions require lifecycle and mortgage-state dimensions",
                "nonmodelled_holdout",
                "H08_FTB_PROFILE",
            ),
            AbsentMeasurement(
                "epls_landlord_cross_section",
                "H09 portfolio, leverage, acquisition, and exit moments require landlord identity",
                "nonmodelled_holdout",
                "H09_EPLS_2018",
            ),
            AbsentMeasurement(
                "uk_residential_transaction_count",
                "H10 is a UK count and cannot be substituted for England turnover per dwelling",
                "nonmodelled_holdout",
                "H10_HMRC_TX",
            ),
            AbsentMeasurement(
                "hpi_buyer_category_cuts",
                "H11 purchaser and finance cuts do not identify landlords or aggregate HPI",
                "nonmodelled_holdout",
                "H11_HPI_BUYER_CUTS",
            ),
            AbsentMeasurement(
                "post_2019_regime_outcomes",
                "H12 lies outside the 2008--2019 state axis and is a separate regime exercise",
                "nonmodelled_holdout",
                "H12_POST2019",
            ),
        )
    }
)


UNAVAILABLE_RESPONSE_MEASUREMENTS = MappingProxyType(
    {
        **ABSENT_PUBLIC_CORE_MEASUREMENTS,
        **PENDING_PUBLIC_CORE_TARGETS,
        **NONMODELLED_PUBLIC_CORE_HOLDOUTS,
    }
)


# The annual moment loadings are stated in natural response units per normalised
# shock-amplitude unit.  They are design coefficients for an identification
# stress test, not estimated elasticities or empirical findings.
MOMENT_NAMES: tuple[str, ...] = (
    "owner_share_25_44_pp",
    "private_renter_share_25_44_pp",
    "nhw_top10_share_pp",
    "log_hpi_pct",
    "private_rent_pct",
    "net_additions_rate_pp",
    "owner_mortgage_rate_pp",
    "btl_owner_spread_pp",
    "price_rent_index_pct",
    "turnover_pct",
    "prs_dwelling_share_pp",
)

_BASE_COEFFICIENTS: NDArray[np.float64] = np.asarray(
    [
        # z_top, z_mid, credit, supply, tax, rate, demographics
        [-1.45, 1.80, 1.20, 0.80, 0.35, -0.90, -0.40],  # owner share
        [1.10, -1.20, -0.70, -0.25, -0.60, 0.70, 0.55],  # private renter share
        [1.70, -0.35, 0.05, 0.00, 0.00, 0.15, 0.00],  # top NHW share
        [5.80, 3.00, 5.20, -3.80, -1.30, -4.50, 2.00],  # HPI
        [1.30, 1.70, 0.80, -1.40, 1.40, -0.30, 1.80],  # private rent
        [0.20, 0.10, 0.20, 1.80, -0.15, -0.35, 0.40],  # net additions
        [0.05, 0.00, -1.20, 0.00, 0.00, 1.60, 0.02],  # owner mortgage rate
        [-0.05, 0.00, -0.60, 0.00, 1.10, 0.20, 0.00],  # BTL-owner spread
        [4.50, 1.30, 4.40, -2.40, -2.70, -4.20, 0.20],  # price/rent index
        [1.80, 1.00, 3.80, 1.50, -2.60, -3.00, 0.80],  # turnover
        [0.80, -0.80, -0.30, 0.20, -0.70, 0.40, 0.30],  # PRS dwelling share
    ],
    dtype=float,
)


def common_ramp(years: Sequence[int] = YEARS) -> NDArray[np.float64]:
    """Return the preregistered common linear ramp, normalised from zero to one."""

    year_tuple = tuple(int(year) for year in years)
    if len(year_tuple) < 2:
        raise InvariantViolation("the common ramp requires at least two years")
    if any(right <= left for left, right in zip(year_tuple, year_tuple[1:])):
        raise InvariantViolation("ramp years must be strictly increasing and unique")
    span = year_tuple[-1] - year_tuple[0]
    if span <= 0:
        raise InvariantViolation("the common ramp has a non-positive time span")
    ramp = np.asarray([(year - year_tuple[0]) / span for year in year_tuple], dtype=float)
    ramp.setflags(write=False)
    return ramp


def _annual_observations(
    prefix: str,
    moment: str,
    years: Iterable[int],
    *,
    role: str,
    geography: str,
    unit: str,
    financial_year: bool = False,
    adapter: str = "identity_deviation",
) -> list[ObservationSpec]:
    observations: list[ObservationSpec] = []
    for year in years:
        period = f"{year}-{str(year + 1)[-2:]}" if financial_year else str(year)
        observations.append(
            ObservationSpec(
                observation_id=f"{prefix}_{period.replace('-', '_')}",
                moment=moment,
                anchor_year=year,
                period=period,
                role=role,
                geography=geography,
                unit=unit,
                adapter=adapter,
            )
        )
    return observations


def _build_modelled_public_core_schedule() -> tuple[ObservationSpec, ...]:
    """Build the dated subset with a defensible direct local-response map."""

    observations = [
        ObservationSpec(
            "T01_O_BASE",
            "owner_share_25_44_pp",
            2008,
            "2008-09",
            TARGET_ROLE,
            "England",
            "percentage level",
            "owner_share_level",
        ),
        ObservationSpec(
            "T02_O_END",
            "owner_share_25_44_pp",
            2018,
            "2018-19",
            TARGET_ROLE,
            "England",
            "percentage level",
            "owner_share_level",
        ),
        ObservationSpec(
            "T03_PRS_BASE",
            "private_renter_share_25_44_pp",
            2008,
            "2008-09",
            TARGET_ROLE,
            "England",
            "percentage level",
            "private_renter_share_level",
        ),
        ObservationSpec(
            "T04_PRS_END",
            "private_renter_share_25_44_pp",
            2018,
            "2018-19",
            TARGET_ROLE,
            "England",
            "percentage level",
            "private_renter_share_level",
        ),
    ]

    # Survey field periods retain their full labels.  The midpoint-like annual
    # anchors are an explicit projection convention for this prototype only.
    for suffix, period, anchor in (
        ("W2", "Wave 2 (2008-10)", 2009),
        ("W3", "Wave 3 (2010-12)", 2011),
        ("W4", "Wave 4 (2012-14)", 2013),
        ("W5", "Wave 5 (2014-16)", 2015),
        ("R6", "Round 6 (2016-18)", 2017),
    ):
        observations.append(
            ObservationSpec(
                f"T05_NHW_TOP10_{suffix}",
                "nhw_top10_share_pp",
                anchor,
                period,
                TARGET_ROLE,
                "Great Britain",
                "percentage-point deviation",
            )
        )

    observations.extend(
        _annual_observations(
            "T06_HPI",
            "log_hpi_pct",
            YEARS,
            role=TARGET_ROLE,
            geography="England",
            unit="log-percent deviation",
        )
    )
    observations.append(
        ObservationSpec(
            "T07_RENT_END",
            "private_rent_pct",
            2018,
            "2018-19",
            TARGET_ROLE,
            "England",
            "nominal pounds per week",
            "nominal_rent_level_from_log_pct",
        )
    )
    observations.extend(
        _annual_observations(
            "T08_NET_ADDITIONS",
            "net_additions_rate_pp",
            range(2008, 2019),
            role=TARGET_ROLE,
            geography="England",
            unit="percentage-point deviation",
            financial_year=True,
        )
    )
    observations.extend(
        _annual_observations(
            "T09_OO_RATE",
            "owner_mortgage_rate_pp",
            YEARS,
            role=TARGET_ROLE,
            geography="United Kingdom",
            unit="percentage-point deviation",
        )
    )
    observations.extend(
        _annual_observations(
            "T10_BTL_SPREAD",
            "btl_owner_spread_pp",
            YEARS,
            role=TARGET_ROLE,
            geography="United Kingdom",
            unit="percentage-point deviation",
        )
    )

    # H01 is observed annually but remains prospectively frozen.  The response
    # map can represent both tenure shares directly, so all strict midpath years
    # belong in the schedule even though they never enter the fitting objective.
    observations.extend(
        _annual_observations(
            "H01_OWNER",
            "owner_share_25_44_pp",
            range(2009, 2018),
            role=DIAGNOSTIC_ROLE,
            geography="England",
            unit="percentage level",
            financial_year=True,
            adapter="owner_share_level",
        )
    )
    observations.extend(
        _annual_observations(
            "H01_PRS",
            "private_renter_share_25_44_pp",
            range(2009, 2018),
            role=DIAGNOSTIC_ROLE,
            geography="England",
            unit="percentage level",
            financial_year=True,
            adapter="private_renter_share_level",
        )
    )

    # H05 remains non-modelled because its frozen schedule is monthly, while
    # this state system is annual and has no preregistered interpolation map.
    observations.extend(
        _annual_observations(
            "H06_TURNOVER",
            "turnover_pct",
            YEARS,
            role=DIAGNOSTIC_ROLE,
            geography="England",
            unit="percent deviation in Category A sales per 1,000 dwellings",
        )
    )

    observation_ids = [item.observation_id for item in observations]
    if len(observation_ids) != len(set(observation_ids)):
        raise InvariantViolation("modelled public-core observation IDs are not unique")
    if any(item.moment not in MOMENT_NAMES for item in observations):
        raise InvariantViolation(
            "modelled public-core schedule references an unknown response moment"
        )
    if any(item.moment in UNAVAILABLE_RESPONSE_MEASUREMENTS for item in observations):
        raise InvariantViolation(
            "an absent or non-modelled measurement entered the modelled schedule"
        )
    return tuple(observations)


MODELLED_PUBLIC_CORE_OBSERVATIONS: tuple[ObservationSpec, ...] = (
    _build_modelled_public_core_schedule()
)

# Backward-compatible spelling.  This is the modelled subset, not a claim that
# every preregistered holdout has a defensible local-response representation.
PUBLIC_CORE_OBSERVATIONS = MODELLED_PUBLIC_CORE_OBSERVATIONS


@dataclass(frozen=True, slots=True)
class ResponsePanel:
    """Annual response deviations for the directly modelled moment set."""

    years: tuple[int, ...]
    moments: tuple[str, ...]
    values: NDArray[np.float64]
    source: str = "local_response"

    def __post_init__(self) -> None:
        values = np.asarray(self.values, dtype=float).copy()
        expected_shape = (len(self.years), len(self.moments))
        if values.shape != expected_shape:
            raise InvariantViolation(
                f"response panel shape {values.shape} does not match {expected_shape}"
            )
        if not np.all(np.isfinite(values)):
            raise InvariantViolation("response panel contains non-finite modelled values")
        if len(set(self.years)) != len(self.years) or tuple(sorted(self.years)) != self.years:
            raise InvariantViolation("response panel years must be sorted and unique")
        if len(set(self.moments)) != len(self.moments):
            raise InvariantViolation("response panel moments must be unique")
        if set(self.moments) & set(UNAVAILABLE_RESPONSE_MEASUREMENTS):
            raise InvariantViolation(
                "absent or non-modelled measurements cannot enter a response panel"
            )
        values.setflags(write=False)
        object.__setattr__(self, "values", values)

    def value(self, moment: str, year: int) -> float:
        """Return a modelled response, raising for unavailable public objects."""

        if moment in UNAVAILABLE_RESPONSE_MEASUREMENTS:
            metadata = UNAVAILABLE_RESPONSE_MEASUREMENTS[moment]
            raise InvariantViolation(
                f"{moment!r} is {metadata.status.replace('_', ' ')}: {metadata.reason}"
            )
        if moment not in self.moments:
            raise InvariantViolation(f"unknown response moment: {moment!r}")
        if year not in self.years:
            raise InvariantViolation(f"year {year} is outside this response panel")
        return float(self.values[self.years.index(year), self.moments.index(moment)])

    def optional_value(self, moment: str, year: int) -> float | None:
        """Return ``None`` for absent or non-modelled objects, never numeric zero."""

        if moment in UNAVAILABLE_RESPONSE_MEASUREMENTS:
            return None
        return self.value(moment, year)


class LocalResponseModel:
    """Linear annual response design with an exact analytic Jacobian."""

    def __init__(
        self,
        coefficients: NDArray[np.float64] | Sequence[Sequence[float]] | None = None,
        *,
        variant: str = "baseline",
        use_executable_wealth_bridge: bool | None = None,
    ) -> None:
        matrix = (
            _BASE_COEFFICIENTS if coefficients is None else np.asarray(coefficients, dtype=float)
        )
        matrix = np.asarray(matrix, dtype=float).copy()
        expected_shape = (len(MOMENT_NAMES), len(BLOCK_NAMES))
        if matrix.shape != expected_shape:
            raise InvariantViolation(
                f"coefficient matrix shape {matrix.shape} does not match {expected_shape}"
            )
        if not np.all(np.isfinite(matrix)):
            raise InvariantViolation("coefficient matrix contains non-finite values")
        if not variant:
            raise InvariantViolation("response-model variant must be named")
        matrix.setflags(write=False)
        self._coefficients = matrix
        self.variant = variant
        self.years = YEARS
        self.ramp = common_ramp(self.years)
        use_bridge = (
            coefficients is None
            if use_executable_wealth_bridge is None
            else bool(use_executable_wealth_bridge)
        )
        self._wealth_bridge = LocalWealthMeasurementBridge() if use_bridge else None
        if self._wealth_bridge is not None:
            if self._wealth_bridge.config.years != self.years:
                raise InvariantViolation(
                    "wealth measurement bridge and response model use different year axes"
                )
            terminal = self._wealth_bridge.local_sensitivity_path()[-1]
            wealth_row = MOMENT_NAMES.index("nhw_top10_share_pp")
            top_column = BLOCK_NAMES.index("z_top")
            middle_column = BLOCK_NAMES.index("z_middle")
            expected = matrix[wealth_row, (top_column, middle_column)]
            if not np.allclose(terminal, expected, rtol=0.0, atol=1e-12):
                raise InvariantViolation(
                    "wealth bridge terminal tangent disagrees with the response design"
                )

    @classmethod
    def baseline(cls) -> LocalResponseModel:
        """Construct the preregistered transparent baseline design."""

        return cls(variant="baseline")

    @classmethod
    def known_negative_collinear(
        cls,
        *,
        near: bool = False,
        gap: float = 1e-7,
    ) -> LocalResponseModel:
        """Construct a deliberate top/middle non-identification control.

        In the exact case the two columns are identical.  In the near case a
        small, declared perturbation preserves algebraic rank while producing
        ill-conditioned geometry.  This mutation must fail or visibly weaken a
        rank/conditioning gate.
        """

        if not np.isfinite(gap) or gap <= 0:
            raise InvariantViolation("near-collinearity gap must be finite and positive")
        matrix = _BASE_COEFFICIENTS.copy()
        top_index = BLOCK_NAMES.index("z_top")
        middle_index = BLOCK_NAMES.index("z_middle")
        matrix[:, middle_index] = matrix[:, top_index]
        variant = "known_negative_exact_top_middle_collinearity"
        if near:
            # Remove from a fixed probe vector everything already spanned by
            # the six non-middle columns.  The residual is guaranteed to add a
            # new direction, while ``gap`` controls how nearly collinear it is.
            other_columns = np.delete(matrix, middle_index, axis=1)
            probe = np.linspace(-1.0, 1.0, len(MOMENT_NAMES), dtype=float)
            projection, _, _, _ = np.linalg.lstsq(other_columns, probe, rcond=None)
            direction = probe - other_columns @ projection
            norm = float(np.linalg.norm(direction))
            if norm <= np.finfo(float).eps:
                raise InvariantViolation("near-collinearity probe lies in the fitted column span")
            matrix[:, middle_index] += gap * direction / norm
            variant = f"known_negative_near_top_middle_collinearity_gap_{gap:g}"
        return cls(
            matrix,
            variant=variant,
            use_executable_wealth_bridge=False,
        )

    @property
    def coefficients(self) -> NDArray[np.float64]:
        """Return a defensive copy of the moment-by-block response matrix."""

        return self._coefficients.copy()

    def coefficient(self, moment: str, block: str) -> float:
        canonical = self.canonical_block_name(block)
        if moment not in MOMENT_NAMES:
            raise InvariantViolation(f"unknown response moment: {moment!r}")
        return float(self._coefficients[MOMENT_NAMES.index(moment), BLOCK_NAMES.index(canonical)])

    @staticmethod
    def canonical_block_name(block: str) -> str:
        canonical = BLOCK_ALIASES.get(block, block)
        if canonical not in BLOCK_NAMES:
            raise InvariantViolation(f"unknown shock block: {block!r}")
        return canonical

    @staticmethod
    def zero_amplitudes() -> dict[str, float]:
        return {name: 0.0 for name in BLOCK_NAMES}

    def amplitude_vector(
        self,
        amplitudes: Mapping[str, float] | Sequence[float] | NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Validate and canonicalise a complete seven-block amplitude vector."""

        if isinstance(amplitudes, Mapping):
            canonical: dict[str, float] = {}
            for name, value in amplitudes.items():
                canonical_name = self.canonical_block_name(name)
                if canonical_name in canonical:
                    raise InvariantViolation(
                        f"shock block {canonical_name!r} was supplied more than once via aliases"
                    )
                canonical[canonical_name] = float(value)
            missing = [name for name in BLOCK_NAMES if name not in canonical]
            if missing:
                raise InvariantViolation(
                    "amplitude mapping must state every block explicitly; missing "
                    + ", ".join(missing)
                )
            vector = np.asarray([canonical[name] for name in BLOCK_NAMES], dtype=float)
        else:
            vector = np.asarray(amplitudes, dtype=float)
            if vector.ndim != 1:
                raise InvariantViolation("amplitudes must be a one-dimensional vector")
            if vector.size != len(BLOCK_NAMES):
                raise InvariantViolation(
                    f"expected {len(BLOCK_NAMES)} amplitudes, received {vector.size}"
                )
            vector = vector.copy()
        if not np.all(np.isfinite(vector)):
            raise InvariantViolation("shock amplitudes must all be finite")
        vector.setflags(write=False)
        return vector

    def shock_paths(
        self,
        amplitudes: Mapping[str, float] | Sequence[float] | NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """Return year-by-block paths; every column uses the identical ramp."""

        vector = self.amplitude_vector(amplitudes)
        paths = self.ramp[:, np.newaxis] * vector[np.newaxis, :]
        paths.setflags(write=False)
        return paths

    def predict(
        self,
        amplitudes: Mapping[str, float] | Sequence[float] | NDArray[np.float64],
    ) -> ResponsePanel:
        """Compute annual response deviations for all modelled moments."""

        vector = self.amplitude_vector(amplitudes)
        terminal_response = self._coefficients @ vector
        values = self.ramp[:, np.newaxis] * terminal_response[np.newaxis, :]
        if self._wealth_bridge is not None:
            wealth_index = MOMENT_NAMES.index("nhw_top10_share_pp")
            top_index = BLOCK_NAMES.index("z_top")
            middle_index = BLOCK_NAMES.index("z_middle")
            # Remove the generic contemporaneous-ramp contribution of the two
            # focal flows, then insert the executable accumulated-stock tangent.
            generic_focal = (
                self._coefficients[wealth_index, top_index] * vector[top_index]
                + self._coefficients[wealth_index, middle_index] * vector[middle_index]
            )
            focal_amplitudes = vector[[top_index, middle_index]]
            wealth_tangent = self._wealth_bridge.local_sensitivity_path() @ focal_amplitudes
            values[:, wealth_index] = (
                values[:, wealth_index] - self.ramp * generic_focal + wealth_tangent
            )
        return ResponsePanel(self.years, MOMENT_NAMES, values, source=self.variant)

    def observation_schedule(self, role: str | None = TARGET_ROLE) -> tuple[ObservationSpec, ...]:
        """Return observed entries, optionally including all registered roles."""

        if role is None:
            return MODELLED_PUBLIC_CORE_OBSERVATIONS
        if role not in VALID_ROLES:
            raise InvariantViolation(f"unknown observation role: {role!r}")
        return tuple(item for item in MODELLED_PUBLIC_CORE_OBSERVATIONS if item.role == role)

    def observation_labels(self, role: str | None = TARGET_ROLE) -> tuple[str, ...]:
        return tuple(item.observation_id for item in self.observation_schedule(role))

    def vector_from_panel(
        self,
        panel: ResponsePanel,
        role: str | None = TARGET_ROLE,
    ) -> NDArray[np.float64]:
        """Flatten a response panel on the registered observed schedule."""

        values = np.asarray(
            [
                panel.value(item.moment, item.anchor_year)
                for item in self.observation_schedule(role)
            ],
            dtype=float,
        )
        values.setflags(write=False)
        return values

    def observation_vector(
        self,
        amplitudes: Mapping[str, float] | Sequence[float] | NDArray[np.float64],
        role: str | None = TARGET_ROLE,
    ) -> NDArray[np.float64]:
        return self.vector_from_panel(self.predict(amplitudes), role)

    def analytic_jacobian(self, role: str | None = TARGET_ROLE) -> NDArray[np.float64]:
        """Return the exact observation-by-amplitude Jacobian."""

        rows = []
        year_index = {year: index for index, year in enumerate(self.years)}
        for item in self.observation_schedule(role):
            moment_index = MOMENT_NAMES.index(item.moment)
            ramp_index = year_index[item.anchor_year]
            row = self.ramp[ramp_index] * self._coefficients[moment_index, :]
            if item.moment == "nhw_top10_share_pp" and self._wealth_bridge is not None:
                row = row.copy()
                row[BLOCK_NAMES.index("z_top")] = self._wealth_bridge.local_sensitivity_path()[
                    ramp_index, 0
                ]
                row[BLOCK_NAMES.index("z_middle")] = self._wealth_bridge.local_sensitivity_path()[
                    ramp_index, 1
                ]
            rows.append(row)
        jacobian = np.asarray(rows, dtype=float)
        jacobian.setflags(write=False)
        return jacobian

    # ``jacobian`` is the concise public spelling used by downstream gates.
    jacobian = analytic_jacobian

    def finite_difference_jacobian(
        self,
        amplitudes: Mapping[str, float] | Sequence[float] | NDArray[np.float64] | None = None,
        *,
        step: float = 0.01,
        role: str | None = TARGET_ROLE,
    ) -> NDArray[np.float64]:
        """Central-difference audit of the analytic Jacobian."""

        if not np.isfinite(step) or step <= 0:
            raise InvariantViolation("finite-difference step must be finite and positive")
        base = (
            np.zeros(len(BLOCK_NAMES), dtype=float)
            if amplitudes is None
            else self.amplitude_vector(amplitudes).copy()
        )
        columns: list[NDArray[np.float64]] = []
        for index in range(len(BLOCK_NAMES)):
            upper = base.copy()
            lower = base.copy()
            upper[index] += step
            lower[index] -= step
            difference = (
                self.observation_vector(upper, role) - self.observation_vector(lower, role)
            ) / (2.0 * step)
            columns.append(difference)
        jacobian = np.column_stack(columns)
        jacobian.setflags(write=False)
        return jacobian

    def public_core_value(
        self,
        panel: ResponsePanel,
        moment: str,
        year: int,
    ) -> float | None:
        """Read a value while preserving explicit absent/non-modelled semantics."""

        return panel.optional_value(moment, year)

    def verify_measurement_bridge(self) -> None:
        """Run the executable D1/D2 incidence-to-stock audit when enabled."""

        if self._wealth_bridge is None:
            raise InvariantViolation(
                "this response-model variant deliberately disables the wealth bridge"
            )
        self._wealth_bridge.verify()


def baseline_model() -> LocalResponseModel:
    """Convenience constructor for callers that prefer a function API."""

    return LocalResponseModel.baseline()


def collinear_known_negative(*, near: bool = False, gap: float = 1e-7) -> LocalResponseModel:
    """Convenience constructor for the preregistered collinearity mutation."""

    return LocalResponseModel.known_negative_collinear(near=near, gap=gap)


__all__ = [
    "ABSENT_PUBLIC_CORE_MEASUREMENTS",
    "BLOCK_ALIASES",
    "BLOCK_NAMES",
    "DIAGNOSTIC_ROLE",
    "MODELLED_PUBLIC_CORE_OBSERVATIONS",
    "MOMENT_NAMES",
    "NONMODELLED_PUBLIC_CORE_HOLDOUTS",
    "PENDING_PUBLIC_CORE_TARGETS",
    "PUBLIC_CORE_OBSERVATIONS",
    "TARGET_ROLE",
    "UNAVAILABLE_RESPONSE_MEASUREMENTS",
    "VALID_ADAPTERS",
    "YEARS",
    "AbsentMeasurement",
    "LocalResponseModel",
    "ObservationSpec",
    "ResponsePanel",
    "baseline_model",
    "collinear_known_negative",
    "common_ramp",
]
