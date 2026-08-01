"""Executable non-housing wealth stock-flow and observation bridge.

The latent resource flow is mapped into active accumulation before wealth is
observed.  Passive non-housing valuation, debt changes, withdrawals, and
population entry/exit remain separate.  Property revaluation is an explicit
forbidden field rather than an undocumented convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable

from .errors import InvariantViolation
from .incidence import DEFAULT_TOLERANCE, IncidenceLedger


class WealthPriceBasis(str, Enum):
    """Price basis for the closing non-housing wealth observation."""

    CURRENT_PRICE = "CURRENT_PRICE"
    CONSTANT_PRICE = "CONSTANT_PRICE"


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise InvariantViolation(f"{name} must be finite")


def _close(left: float, right: float, tolerance: float) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


@dataclass(frozen=True)
class WealthStockFlow:
    """Exact one-period non-housing net-wealth bridge for one model group.

    ``debt_change`` is positive when liabilities increase, so it enters net
    wealth with a minus sign.  ``entry_exit`` is the net stock carried into the
    represented population by entry, exit, mortality, or sample-composition
    change.  The resource pass-through is constrained to [0, 1]; leverage or
    borrowing must be recorded in the debt block rather than hidden in it.
    """

    model_group: str
    year: int
    opening_non_housing_wealth: float
    latent_resource_flow: float
    resource_pass_through: float
    active_accumulation_from_resource: float
    other_active_accumulation: float
    withdrawals: float
    debt_change: float
    realised_returns: float
    non_housing_valuation_change: float
    entry_exit: float
    property_revaluation: float
    closing_current_price_wealth: float
    closing_constant_price_wealth: float
    tolerance: float = DEFAULT_TOLERANCE

    def __post_init__(self) -> None:
        self.validate()

    @property
    def implied_active_accumulation_from_resource(self) -> float:
        return self.latent_resource_flow * self.resource_pass_through

    @property
    def implied_closing_constant_price_wealth(self) -> float:
        return (
            self.opening_non_housing_wealth
            + self.active_accumulation_from_resource
            + self.other_active_accumulation
            - self.withdrawals
            - self.debt_change
            + self.realised_returns
            + self.entry_exit
        )

    @property
    def implied_closing_current_price_wealth(self) -> float:
        return self.implied_closing_constant_price_wealth + self.non_housing_valuation_change

    @property
    def current_price_residual(self) -> float:
        return self.closing_current_price_wealth - self.implied_closing_current_price_wealth

    @property
    def constant_price_residual(self) -> float:
        return self.closing_constant_price_wealth - self.implied_closing_constant_price_wealth

    def closing_wealth(self, basis: WealthPriceBasis) -> float:
        """Return the closing stock on an explicitly declared price basis."""

        self.validate()
        if basis is WealthPriceBasis.CURRENT_PRICE:
            return self.closing_current_price_wealth
        if basis is WealthPriceBasis.CONSTANT_PRICE:
            return self.closing_constant_price_wealth
        raise InvariantViolation("wealth observation requires a registered price basis")

    def validate(self) -> None:
        """Raise unless all bridge identities and exclusion rules hold."""

        if not isinstance(self.model_group, str) or not self.model_group.strip():
            raise InvariantViolation("wealth model group must be a non-empty string")
        if isinstance(self.year, bool) or not isinstance(self.year, int) or self.year <= 0:
            raise InvariantViolation("wealth bridge year must be a positive integer")
        for name, value in (
            ("opening non-housing wealth", self.opening_non_housing_wealth),
            ("latent resource flow", self.latent_resource_flow),
            ("resource pass-through", self.resource_pass_through),
            ("resource-derived accumulation", self.active_accumulation_from_resource),
            ("other active accumulation", self.other_active_accumulation),
            ("withdrawals", self.withdrawals),
            ("debt change", self.debt_change),
            ("realised returns", self.realised_returns),
            ("non-housing valuation change", self.non_housing_valuation_change),
            ("entry/exit", self.entry_exit),
            ("property revaluation", self.property_revaluation),
            ("closing current-price wealth", self.closing_current_price_wealth),
            ("closing constant-price wealth", self.closing_constant_price_wealth),
            ("wealth bridge tolerance", self.tolerance),
        ):
            _require_finite(name, value)
        if self.tolerance <= 0:
            raise InvariantViolation("wealth bridge tolerance must be strictly positive")
        if self.resource_pass_through < 0 or self.resource_pass_through > 1:
            raise InvariantViolation("resource pass-through must lie in [0, 1]")
        if self.other_active_accumulation < -self.tolerance:
            raise InvariantViolation(
                "other active accumulation cannot be negative; record a withdrawal instead"
            )
        if self.withdrawals < -self.tolerance:
            raise InvariantViolation("withdrawals cannot be negative")
        if not _close(self.property_revaluation, 0.0, self.tolerance):
            raise InvariantViolation(
                "property revaluation is forbidden in the non-housing wealth bridge"
            )
        if not _close(
            self.active_accumulation_from_resource,
            self.implied_active_accumulation_from_resource,
            self.tolerance,
        ):
            raise InvariantViolation(
                "latent resource flow does not map to active accumulation at the stated rate"
            )
        if not _close(self.current_price_residual, 0.0, self.tolerance):
            raise InvariantViolation(
                f"current-price stock-flow identity fails: residual={self.current_price_residual}"
            )
        if not _close(self.constant_price_residual, 0.0, self.tolerance):
            raise InvariantViolation(
                f"constant-price stock-flow identity fails: residual={self.constant_price_residual}"
            )


def evolve_non_housing_wealth(
    *,
    model_group: str,
    year: int,
    opening_non_housing_wealth: float,
    latent_resource_flow: float,
    resource_pass_through: float,
    other_active_accumulation: float,
    withdrawals: float,
    debt_change: float,
    realised_returns: float,
    non_housing_valuation_change: float,
    entry_exit: float,
    property_revaluation: float = 0.0,
    tolerance: float = DEFAULT_TOLERANCE,
) -> WealthStockFlow:
    """Evolve one group while retaining every registered stock-flow component."""

    active_from_resource = latent_resource_flow * resource_pass_through
    closing_constant = (
        opening_non_housing_wealth
        + active_from_resource
        + other_active_accumulation
        - withdrawals
        - debt_change
        + realised_returns
        + entry_exit
    )
    closing_current = closing_constant + non_housing_valuation_change
    return WealthStockFlow(
        model_group=model_group,
        year=year,
        opening_non_housing_wealth=opening_non_housing_wealth,
        latent_resource_flow=latent_resource_flow,
        resource_pass_through=resource_pass_through,
        active_accumulation_from_resource=active_from_resource,
        other_active_accumulation=other_active_accumulation,
        withdrawals=withdrawals,
        debt_change=debt_change,
        realised_returns=realised_returns,
        non_housing_valuation_change=non_housing_valuation_change,
        entry_exit=entry_exit,
        property_revaluation=property_revaluation,
        closing_current_price_wealth=closing_current,
        closing_constant_price_wealth=closing_constant,
        tolerance=tolerance,
    )


def validate_incidence_wealth_bridge(
    ledger: IncidenceLedger,
    flows: Iterable[WealthStockFlow],
    *,
    tolerance: float = DEFAULT_TOLERANCE,
) -> None:
    """Verify that dated wealth flows use the ledger's aggregate focal shocks."""

    if not isinstance(ledger, IncidenceLedger):
        raise InvariantViolation("incidence-to-wealth validation requires an IncidenceLedger")
    ledger.validate()
    _require_finite("incidence bridge tolerance", tolerance)
    if tolerance <= 0:
        raise InvariantViolation("incidence bridge tolerance must be strictly positive")

    by_group: dict[str, WealthStockFlow] = {}
    for flow in flows:
        if not isinstance(flow, WealthStockFlow):
            raise InvariantViolation("all incidence bridge records must be WealthStockFlow values")
        flow.validate()
        if flow.model_group in by_group:
            raise InvariantViolation(f"duplicate wealth flow for group {flow.model_group!r}")
        by_group[flow.model_group] = flow
    if set(by_group) != {"top", "middle"}:
        raise InvariantViolation("incidence bridge requires exactly the 'top' and 'middle' groups")
    if any(flow.year != ledger.year for flow in by_group.values()):
        raise InvariantViolation("wealth-flow and incidence-ledger years do not match")
    if not _close(by_group["top"].latent_resource_flow, ledger.top.aggregate_delta, tolerance):
        raise InvariantViolation("top wealth bridge does not use the aggregate top incidence")
    if not _close(
        by_group["middle"].latent_resource_flow,
        ledger.middle.aggregate_delta,
        tolerance,
    ):
        raise InvariantViolation("middle wealth bridge does not use the aggregate middle incidence")


@dataclass(frozen=True)
class RankWeight:
    """Map one permanent model group into one round-specific observed rank."""

    model_group: str
    observed_rank: str
    opening_weight: float
    closing_weight: float

    def __post_init__(self) -> None:
        if not isinstance(self.model_group, str) or not self.model_group.strip():
            raise InvariantViolation("rank weight model group must be a non-empty string")
        if not isinstance(self.observed_rank, str) or not self.observed_rank.strip():
            raise InvariantViolation("observed wealth rank must be a non-empty string")
        for name, value in (
            ("opening rank weight", self.opening_weight),
            ("closing rank weight", self.closing_weight),
        ):
            _require_finite(name, value)
            if value < 0 or value > 1:
                raise InvariantViolation(f"{name} must lie in [0, 1]")


@dataclass(frozen=True)
class WealthObservationMap:
    """Declared model-type to observed-rank map for a wealth-share moment."""

    mapping_id: str
    geography: str
    top_rank: str
    price_basis: WealthPriceBasis
    rank_weights: tuple[RankWeight, ...]
    tolerance: float = DEFAULT_TOLERANCE

    def __post_init__(self) -> None:
        self.validate()

    @property
    def model_groups(self) -> tuple[str, ...]:
        return tuple(sorted({item.model_group for item in self.rank_weights}))

    @property
    def observed_ranks(self) -> tuple[str, ...]:
        return tuple(sorted({item.observed_rank for item in self.rank_weights}))

    def validate(self) -> None:
        """Raise unless opening and closing rank allocations are both exhaustive."""

        for name, value in (
            ("mapping id", self.mapping_id),
            ("mapping geography", self.geography),
            ("top rank", self.top_rank),
        ):
            if not isinstance(value, str) or not value.strip():
                raise InvariantViolation(f"{name} must be a non-empty string")
        if not isinstance(self.price_basis, WealthPriceBasis):
            raise InvariantViolation("wealth mapping requires a registered price basis")
        _require_finite("wealth mapping tolerance", self.tolerance)
        if self.tolerance <= 0:
            raise InvariantViolation("wealth mapping tolerance must be strictly positive")
        if not isinstance(self.rank_weights, tuple) or not self.rank_weights:
            raise InvariantViolation("wealth mapping requires a non-empty tuple of rank weights")
        if any(not isinstance(item, RankWeight) for item in self.rank_weights):
            raise InvariantViolation("wealth mapping contains a non-RankWeight entry")

        pairs = [(item.model_group, item.observed_rank) for item in self.rank_weights]
        if len(set(pairs)) != len(pairs):
            raise InvariantViolation("wealth mapping contains a duplicate group/rank pair")
        if self.top_rank not in self.observed_ranks:
            raise InvariantViolation("declared top rank is absent from the wealth mapping")
        if len(self.observed_ranks) < 2:
            raise InvariantViolation("a top-share observation requires at least two observed ranks")
        if set(self.model_groups) & set(self.observed_ranks):
            raise InvariantViolation(
                "permanent model groups and observed ranks must use distinct labels"
            )

        for group in self.model_groups:
            entries = [item for item in self.rank_weights if item.model_group == group]
            opening_sum = sum(item.opening_weight for item in entries)
            closing_sum = sum(item.closing_weight for item in entries)
            if not _close(opening_sum, 1.0, self.tolerance):
                raise InvariantViolation(f"opening rank weights for {group!r} do not sum to one")
            if not _close(closing_sum, 1.0, self.tolerance):
                raise InvariantViolation(f"closing rank weights for {group!r} do not sum to one")


def _pairs_to_dict(name: str, pairs: tuple[tuple[str, float], ...]) -> dict[str, float]:
    result: dict[str, float] = {}
    for label, value in pairs:
        if label in result:
            raise InvariantViolation(f"{name} contains duplicate label {label!r}")
        _require_finite(f"{name} value", value)
        result[label] = value
    return result


@dataclass(frozen=True)
class ObservedNonHousingWealth:
    """Observed rank stocks and an exact top-share change decomposition."""

    mapping_id: str
    geography: str
    year: int
    price_basis: WealthPriceBasis
    top_rank: str
    opening_rank_stocks: tuple[tuple[str, float], ...]
    closing_stocks_at_opening_ranks: tuple[tuple[str, float], ...]
    closing_rank_stocks: tuple[tuple[str, float], ...]
    opening_denominator: float
    closing_denominator: float
    opening_top_share: float
    closing_top_share: float
    stock_flow_numerator_effect: float
    rank_reclassification_effect: float
    denominator_effect: float
    decomposition_residual: float
    tolerance: float = DEFAULT_TOLERANCE

    def __post_init__(self) -> None:
        self.validate()

    @property
    def top_share_change(self) -> float:
        return self.closing_top_share - self.opening_top_share

    def validate(self) -> None:
        """Recompute the observation and decomposition from the stored rank stocks."""

        if not isinstance(self.mapping_id, str) or not self.mapping_id.strip():
            raise InvariantViolation("observed wealth mapping id must be non-empty")
        if not isinstance(self.geography, str) or not self.geography.strip():
            raise InvariantViolation("observed wealth geography must be non-empty")
        if isinstance(self.year, bool) or not isinstance(self.year, int) or self.year <= 0:
            raise InvariantViolation("observed wealth year must be a positive integer")
        if not isinstance(self.price_basis, WealthPriceBasis):
            raise InvariantViolation("observed wealth requires a registered price basis")
        _require_finite("observed wealth tolerance", self.tolerance)
        if self.tolerance <= 0:
            raise InvariantViolation("observed wealth tolerance must be strictly positive")
        rank_stock_sets = (
            self.opening_rank_stocks,
            self.closing_stocks_at_opening_ranks,
            self.closing_rank_stocks,
        )
        if any(not isinstance(items, tuple) for items in rank_stock_sets):
            raise InvariantViolation("observed rank stocks must be immutable tuples")

        opening = _pairs_to_dict("opening rank stocks", self.opening_rank_stocks)
        closing_at_open = _pairs_to_dict(
            "closing stocks at opening ranks", self.closing_stocks_at_opening_ranks
        )
        closing = _pairs_to_dict("closing rank stocks", self.closing_rank_stocks)
        if not opening or set(opening) != set(closing_at_open) or set(opening) != set(closing):
            raise InvariantViolation("opening and closing observed-rank sets must match")
        if self.top_rank not in opening:
            raise InvariantViolation("observed top rank is absent from rank stocks")

        for name, value in (
            ("opening denominator", self.opening_denominator),
            ("closing denominator", self.closing_denominator),
            ("opening top share", self.opening_top_share),
            ("closing top share", self.closing_top_share),
            ("stock-flow numerator effect", self.stock_flow_numerator_effect),
            ("rank reclassification effect", self.rank_reclassification_effect),
            ("denominator effect", self.denominator_effect),
            ("decomposition residual", self.decomposition_residual),
        ):
            _require_finite(name, value)
        if self.opening_denominator <= 0 or self.closing_denominator <= 0:
            raise InvariantViolation("wealth-share denominators must be strictly positive")
        if not _close(self.opening_denominator, sum(opening.values()), self.tolerance):
            raise InvariantViolation("opening wealth-share denominator is inconsistent")
        if not _close(self.closing_denominator, sum(closing.values()), self.tolerance):
            raise InvariantViolation("closing wealth-share denominator is inconsistent")
        if not _close(self.closing_denominator, sum(closing_at_open.values()), self.tolerance):
            raise InvariantViolation(
                "closing stocks mapped at opening ranks do not preserve the denominator"
            )

        n0 = opening[self.top_rank]
        n_flow = closing_at_open[self.top_rank]
        n1 = closing[self.top_rank]
        expected_open_share = n0 / self.opening_denominator
        expected_close_share = n1 / self.closing_denominator
        expected_stock_flow = (n_flow - n0) / self.opening_denominator
        expected_reclassification = (n1 - n_flow) / self.opening_denominator
        expected_denominator = n1 * (
            1.0 / self.closing_denominator - 1.0 / self.opening_denominator
        )
        expected_residual = (
            expected_close_share
            - expected_open_share
            - expected_stock_flow
            - expected_reclassification
            - expected_denominator
        )
        checks = (
            ("opening top share", self.opening_top_share, expected_open_share),
            ("closing top share", self.closing_top_share, expected_close_share),
            ("stock-flow numerator effect", self.stock_flow_numerator_effect, expected_stock_flow),
            (
                "rank reclassification effect",
                self.rank_reclassification_effect,
                expected_reclassification,
            ),
            ("denominator effect", self.denominator_effect, expected_denominator),
            ("share decomposition residual", self.decomposition_residual, expected_residual),
        )
        for name, actual, expected in checks:
            if not _close(actual, expected, self.tolerance):
                raise InvariantViolation(f"{name} is inconsistent with observed rank stocks")
        if not _close(self.decomposition_residual, 0.0, self.tolerance):
            raise InvariantViolation(
                f"top-share decomposition does not close: residual={self.decomposition_residual}"
            )


def observe_non_housing_wealth(
    flows: Iterable[WealthStockFlow],
    mapping: WealthObservationMap,
) -> ObservedNonHousingWealth:
    """Map permanent groups to ranks and compute the exact denominator effect."""

    if not isinstance(mapping, WealthObservationMap):
        raise InvariantViolation("wealth observation requires a WealthObservationMap")
    mapping.validate()
    by_group: dict[str, WealthStockFlow] = {}
    for flow in flows:
        if not isinstance(flow, WealthStockFlow):
            raise InvariantViolation("all wealth observations must be WealthStockFlow values")
        flow.validate()
        if flow.model_group in by_group:
            raise InvariantViolation(f"duplicate wealth flow for group {flow.model_group!r}")
        by_group[flow.model_group] = flow
    if set(by_group) != set(mapping.model_groups):
        raise InvariantViolation("wealth flows do not match the observation map's model groups")
    years = {flow.year for flow in by_group.values()}
    if len(years) != 1:
        raise InvariantViolation("wealth observation cannot combine different flow years")
    year = next(iter(years))

    opening = {rank: 0.0 for rank in mapping.observed_ranks}
    closing_at_open = {rank: 0.0 for rank in mapping.observed_ranks}
    closing = {rank: 0.0 for rank in mapping.observed_ranks}
    for item in mapping.rank_weights:
        flow = by_group[item.model_group]
        close_stock = flow.closing_wealth(mapping.price_basis)
        opening[item.observed_rank] += item.opening_weight * flow.opening_non_housing_wealth
        closing_at_open[item.observed_rank] += item.opening_weight * close_stock
        closing[item.observed_rank] += item.closing_weight * close_stock

    opening_denominator = sum(opening.values())
    closing_denominator = sum(closing.values())
    if opening_denominator <= 0 or closing_denominator <= 0:
        raise InvariantViolation("wealth-share denominators must be strictly positive")
    n0 = opening[mapping.top_rank]
    n_flow = closing_at_open[mapping.top_rank]
    n1 = closing[mapping.top_rank]
    opening_share = n0 / opening_denominator
    closing_share = n1 / closing_denominator
    stock_flow_effect = (n_flow - n0) / opening_denominator
    reclassification_effect = (n1 - n_flow) / opening_denominator
    denominator_effect = n1 * (1.0 / closing_denominator - 1.0 / opening_denominator)
    residual = (
        closing_share
        - opening_share
        - stock_flow_effect
        - reclassification_effect
        - denominator_effect
    )

    return ObservedNonHousingWealth(
        mapping_id=mapping.mapping_id,
        geography=mapping.geography,
        year=year,
        price_basis=mapping.price_basis,
        top_rank=mapping.top_rank,
        opening_rank_stocks=tuple(sorted(opening.items())),
        closing_stocks_at_opening_ranks=tuple(sorted(closing_at_open.items())),
        closing_rank_stocks=tuple(sorted(closing.items())),
        opening_denominator=opening_denominator,
        closing_denominator=closing_denominator,
        opening_top_share=opening_share,
        closing_top_share=closing_share,
        stock_flow_numerator_effect=stock_flow_effect,
        rank_reclassification_effect=reclassification_effect,
        denominator_effect=denominator_effect,
        decomposition_residual=residual,
        tolerance=mapping.tolerance,
    )
