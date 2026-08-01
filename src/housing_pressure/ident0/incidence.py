"""Failure-closed units and resource closures for IDENT-0 experiments.

The focal shocks are aggregate resource flows.  A per-recipient amount is a
different object until it has been multiplied by the corresponding recipient
mass.  This module stores both representations and the representation that was
actually stated, so a unit-label mutation cannot pass silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import hmac
import json
import math

from .errors import InvariantViolation


DEFAULT_TOLERANCE = 1e-12


class UnitConvention(str, Enum):
    """Unit in which a resource incidence was originally stated."""

    AGGREGATE = "AGGREGATE"
    PER_RECIPIENT = "PER_RECIPIENT"


class ClosureClass(str, Enum):
    """Permitted diagnostic closures from the amended preregistration."""

    D1_RESOURCE_INJECTION = "D1_RESOURCE_INJECTION"
    D1R_TOP_RESOURCE_WITHDRAWAL = "D1R_TOP_RESOURCE_WITHDRAWAL"
    D2_RESOURCE_LOSS = "D2_RESOURCE_LOSS"
    D2R_MIDDLE_RESOURCE_INJECTION = "D2R_MIDDLE_RESOURCE_INJECTION"
    E0_REDISTRIBUTION = "E0_REDISTRIBUTION"


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise InvariantViolation(f"{name} must be finite")


def _close(left: float, right: float, tolerance: float) -> bool:
    return math.isclose(left, right, rel_tol=tolerance, abs_tol=tolerance)


@dataclass(frozen=True)
class ResourceIncidence:
    """One recipient block represented in aggregate and per-recipient units."""

    recipient_group: str
    recipient_mass: float
    stated_amount: float
    stated_unit: UnitConvention
    aggregate_delta: float
    per_recipient_delta: float
    tolerance: float = DEFAULT_TOLERANCE

    def __post_init__(self) -> None:
        self.validate()

    @classmethod
    def from_amount(
        cls,
        recipient_group: str,
        amount: float,
        unit: UnitConvention,
        recipient_mass: float,
        *,
        tolerance: float = DEFAULT_TOLERANCE,
    ) -> ResourceIncidence:
        """Construct both unit representations from one explicitly labelled amount."""

        if not isinstance(unit, UnitConvention):
            raise InvariantViolation("resource incidence unit must be a UnitConvention")
        _require_finite("stated amount", amount)
        _require_finite("recipient mass", recipient_mass)
        if recipient_mass <= 0:
            raise InvariantViolation("recipient mass must be strictly positive")

        if unit is UnitConvention.AGGREGATE:
            aggregate_delta = amount
            per_recipient_delta = amount / recipient_mass
        else:
            aggregate_delta = amount * recipient_mass
            per_recipient_delta = amount
        return cls(
            recipient_group=recipient_group,
            recipient_mass=recipient_mass,
            stated_amount=amount,
            stated_unit=unit,
            aggregate_delta=aggregate_delta,
            per_recipient_delta=per_recipient_delta,
            tolerance=tolerance,
        )

    def validate(self) -> None:
        """Raise if the two unit representations or their provenance disagree."""

        if not isinstance(self.recipient_group, str) or not self.recipient_group.strip():
            raise InvariantViolation("recipient group must be a non-empty string")
        if not isinstance(self.stated_unit, UnitConvention):
            raise InvariantViolation("resource incidence unit must be a UnitConvention")
        for name, value in (
            ("recipient mass", self.recipient_mass),
            ("stated amount", self.stated_amount),
            ("aggregate delta", self.aggregate_delta),
            ("per-recipient delta", self.per_recipient_delta),
            ("incidence tolerance", self.tolerance),
        ):
            _require_finite(name, value)
        if self.recipient_mass <= 0:
            raise InvariantViolation("recipient mass must be strictly positive")
        if self.tolerance <= 0:
            raise InvariantViolation("incidence tolerance must be strictly positive")

        converted = self.recipient_mass * self.per_recipient_delta
        if not _close(self.aggregate_delta, converted, self.tolerance):
            raise InvariantViolation(
                "aggregate/per-recipient incidence mismatch: "
                f"aggregate={self.aggregate_delta}, mass*per_recipient={converted}"
            )

        represented = (
            self.aggregate_delta
            if self.stated_unit is UnitConvention.AGGREGATE
            else self.per_recipient_delta
        )
        if not _close(self.stated_amount, represented, self.tolerance):
            raise InvariantViolation(
                "stated amount does not match its labelled unit representation"
            )

    def canonical_payload(self) -> dict[str, object]:
        """Return the stable, complete payload used by integrity seals."""

        self.validate()
        return {
            "recipient_group": self.recipient_group,
            "recipient_mass": self.recipient_mass,
            "stated_amount": self.stated_amount,
            "stated_unit": self.stated_unit.value,
            "aggregate_delta": self.aggregate_delta,
            "per_recipient_delta": self.per_recipient_delta,
            "tolerance": self.tolerance,
        }


@dataclass(frozen=True)
class IncidenceLedger:
    """A dated two-block experiment and its complete aggregate resource closure."""

    experiment_id: str
    year: int
    closure_class: ClosureClass
    top: ResourceIncidence
    middle: ResourceIncidence
    foreign_transfer_delta: float
    government_absorption_delta: float
    other_household_resource_delta: float
    aggregate_resources_delta: float
    tolerance: float = DEFAULT_TOLERANCE

    def __post_init__(self) -> None:
        self.validate()

    @property
    def accounting_residual(self) -> float:
        """Recorded resource change less the sum of all declared incidence blocks."""

        explained = (
            self.top.aggregate_delta
            + self.middle.aggregate_delta
            + self.other_household_resource_delta
            + self.foreign_transfer_delta
            - self.government_absorption_delta
        )
        return self.aggregate_resources_delta - explained

    @property
    def is_budget_neutral(self) -> bool:
        """Whether the experiment leaves aggregate resources unchanged."""

        return _close(self.aggregate_resources_delta, 0.0, self.tolerance)

    def validate(self) -> None:
        """Raise unless units, accounting, and the named closure all agree."""

        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise InvariantViolation("experiment id must be a non-empty string")
        if isinstance(self.year, bool) or not isinstance(self.year, int) or self.year <= 0:
            raise InvariantViolation("experiment year must be a positive integer")
        if not isinstance(self.closure_class, ClosureClass):
            raise InvariantViolation("closure must be one of the registered closure classes")
        if not isinstance(self.top, ResourceIncidence) or not isinstance(
            self.middle, ResourceIncidence
        ):
            raise InvariantViolation("top and middle incidences must be ResourceIncidence values")
        self.top.validate()
        self.middle.validate()
        if self.top.recipient_group != "top" or self.middle.recipient_group != "middle":
            raise InvariantViolation("resource blocks must be labelled exactly 'top' and 'middle'")
        if not _close(self.top.tolerance, self.tolerance, DEFAULT_TOLERANCE) or not _close(
            self.middle.tolerance, self.tolerance, DEFAULT_TOLERANCE
        ):
            raise InvariantViolation("incidence blocks and ledger must use the same tolerance")

        for name, value in (
            ("foreign transfer delta", self.foreign_transfer_delta),
            ("government absorption delta", self.government_absorption_delta),
            ("other household resource delta", self.other_household_resource_delta),
            ("aggregate resource delta", self.aggregate_resources_delta),
            ("ledger tolerance", self.tolerance),
        ):
            _require_finite(name, value)
        if self.tolerance <= 0:
            raise InvariantViolation("ledger tolerance must be strictly positive")
        if abs(self.accounting_residual) > self.tolerance:
            raise InvariantViolation(
                f"aggregate resource accounting does not close: residual={self.accounting_residual}"
            )

        top_delta = self.top.aggregate_delta
        middle_delta = self.middle.aggregate_delta
        non_focal = (
            self.foreign_transfer_delta,
            self.government_absorption_delta,
            self.other_household_resource_delta,
        )
        if self.closure_class is ClosureClass.D1_RESOURCE_INJECTION:
            if top_delta <= self.tolerance:
                raise InvariantViolation(
                    "D1 requires a strictly positive aggregate top-resource delta"
                )
            if not _close(middle_delta, 0.0, self.tolerance):
                raise InvariantViolation("D1 requires the middle-resource block to be fixed")
            if any(not _close(item, 0.0, self.tolerance) for item in non_focal):
                raise InvariantViolation(
                    "D1 requires fiscal, foreign, and other blocks to be fixed"
                )
            if not _close(self.aggregate_resources_delta, top_delta, self.tolerance):
                raise InvariantViolation(
                    "D1 aggregate resources must rise by the top-resource delta"
                )
        elif self.closure_class is ClosureClass.D1R_TOP_RESOURCE_WITHDRAWAL:
            if top_delta >= -self.tolerance:
                raise InvariantViolation(
                    "D1R requires a strictly negative aggregate top-resource delta"
                )
            if not _close(middle_delta, 0.0, self.tolerance):
                raise InvariantViolation("D1R requires the middle-resource block to be fixed")
            if any(not _close(item, 0.0, self.tolerance) for item in non_focal):
                raise InvariantViolation(
                    "D1R requires fiscal, foreign, and other blocks to be fixed"
                )
            if not _close(self.aggregate_resources_delta, top_delta, self.tolerance):
                raise InvariantViolation(
                    "D1R aggregate resources must fall by the top-resource delta"
                )
        elif self.closure_class is ClosureClass.D2_RESOURCE_LOSS:
            if middle_delta >= -self.tolerance:
                raise InvariantViolation(
                    "D2 requires a strictly negative aggregate middle-resource delta"
                )
            if not _close(top_delta, 0.0, self.tolerance):
                raise InvariantViolation("D2 requires the top-resource block to be fixed")
            if any(not _close(item, 0.0, self.tolerance) for item in non_focal):
                raise InvariantViolation(
                    "D2 requires fiscal, foreign, and other blocks to be fixed"
                )
            if not _close(self.aggregate_resources_delta, middle_delta, self.tolerance):
                raise InvariantViolation(
                    "D2 aggregate resources must fall by the middle-resource delta"
                )
        elif self.closure_class is ClosureClass.D2R_MIDDLE_RESOURCE_INJECTION:
            if middle_delta <= self.tolerance:
                raise InvariantViolation(
                    "D2R requires a strictly positive aggregate middle-resource delta"
                )
            if not _close(top_delta, 0.0, self.tolerance):
                raise InvariantViolation("D2R requires the top-resource block to be fixed")
            if any(not _close(item, 0.0, self.tolerance) for item in non_focal):
                raise InvariantViolation(
                    "D2R requires fiscal, foreign, and other blocks to be fixed"
                )
            if not _close(self.aggregate_resources_delta, middle_delta, self.tolerance):
                raise InvariantViolation(
                    "D2R aggregate resources must rise by the middle-resource delta"
                )
        elif self.closure_class is ClosureClass.E0_REDISTRIBUTION:
            if top_delta <= self.tolerance or middle_delta >= -self.tolerance:
                raise InvariantViolation("E0 requires a top gain and a middle loss")
            if not _close(top_delta, -middle_delta, self.tolerance):
                raise InvariantViolation("E0 requires equal and opposite top/middle deltas")
            if any(not _close(item, 0.0, self.tolerance) for item in non_focal):
                raise InvariantViolation(
                    "E0 requires fiscal, foreign, and other residuals to be zero"
                )
            if not _close(self.aggregate_resources_delta, 0.0, self.tolerance):
                raise InvariantViolation("E0 requires zero aggregate resource change")
        else:
            raise InvariantViolation("unimplemented incidence closure class")

    def canonical_payload(self) -> dict[str, object]:
        """Return a deterministic serialization containing all scientific fields."""

        self.validate()
        return {
            "experiment_id": self.experiment_id,
            "year": self.year,
            "closure_class": self.closure_class.value,
            "top": self.top.canonical_payload(),
            "middle": self.middle.canonical_payload(),
            "foreign_transfer_delta": self.foreign_transfer_delta,
            "government_absorption_delta": self.government_absorption_delta,
            "other_household_resource_delta": self.other_household_resource_delta,
            "aggregate_resources_delta": self.aggregate_resources_delta,
            "tolerance": self.tolerance,
        }

    def fingerprint(self) -> str:
        """Return a SHA-256 integrity fingerprint after revalidating the ledger."""

        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class IncidenceSeal:
    """Detached integrity receipt for a validated incidence ledger."""

    experiment_id: str
    year: int
    sha256: str


@dataclass(frozen=True)
class CompositeIncidenceReceipt:
    """Composition of signed elementary open-economy resource changes.

    An empty child tuple is the explicit no-change anchor.  A non-empty receipt
    preserves each elementary D1/D1R/D2/D2R ledger so arbitrary joint synthetic
    coordinates cannot be mistaken for a single policy closure.
    """

    experiment_id: str
    year: int
    children: tuple[IncidenceLedger, ...]
    aggregate_resources_delta: float
    tolerance: float = DEFAULT_TOLERANCE

    def __post_init__(self) -> None:
        self.validate()

    @property
    def closure_id(self) -> str:
        return "N0_NO_CHANGE" if not self.children else "C0_COMPOSITE_OPEN"

    @property
    def top_aggregate_delta(self) -> float:
        return sum(child.top.aggregate_delta for child in self.children)

    @property
    def middle_aggregate_delta(self) -> float:
        return sum(child.middle.aggregate_delta for child in self.children)

    @property
    def accounting_residual(self) -> float:
        return self.aggregate_resources_delta - sum(
            child.aggregate_resources_delta for child in self.children
        )

    @property
    def is_budget_neutral(self) -> bool:
        return _close(self.aggregate_resources_delta, 0.0, self.tolerance)

    def validate(self) -> None:
        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise InvariantViolation("composite experiment id must be a non-empty string")
        if isinstance(self.year, bool) or not isinstance(self.year, int) or self.year <= 0:
            raise InvariantViolation("composite experiment year must be a positive integer")
        if not isinstance(self.children, tuple):
            raise InvariantViolation("composite incidence children must be an immutable tuple")
        if len(self.children) > 2:
            raise InvariantViolation(
                "a focal composite can contain at most top and middle children"
            )
        _require_finite("composite aggregate resource delta", self.aggregate_resources_delta)
        _require_finite("composite tolerance", self.tolerance)
        if self.tolerance <= 0.0:
            raise InvariantViolation("composite tolerance must be positive")
        permitted = {
            ClosureClass.D1_RESOURCE_INJECTION,
            ClosureClass.D1R_TOP_RESOURCE_WITHDRAWAL,
            ClosureClass.D2_RESOURCE_LOSS,
            ClosureClass.D2R_MIDDLE_RESOURCE_INJECTION,
        }
        top_children = 0
        middle_children = 0
        for child in self.children:
            if not isinstance(child, IncidenceLedger):
                raise InvariantViolation("composite children must be IncidenceLedger values")
            child.validate()
            if child.year != self.year:
                raise InvariantViolation("composite and child years do not match")
            if child.closure_class not in permitted:
                raise InvariantViolation("composite child is not an elementary signed closure")
            if not _close(child.tolerance, self.tolerance, DEFAULT_TOLERANCE):
                raise InvariantViolation("composite and child tolerances must match")
            if child.closure_class in {
                ClosureClass.D1_RESOURCE_INJECTION,
                ClosureClass.D1R_TOP_RESOURCE_WITHDRAWAL,
            }:
                top_children += 1
            else:
                middle_children += 1
        if top_children > 1 or middle_children > 1:
            raise InvariantViolation("composite receipt repeats a focal resource block")
        if not self.children and not _close(self.aggregate_resources_delta, 0.0, self.tolerance):
            raise InvariantViolation("N0 no-change receipt must have zero aggregate change")
        if abs(self.accounting_residual) > self.tolerance:
            raise InvariantViolation(
                f"composite resource accounting does not close: residual={self.accounting_residual}"
            )

    def canonical_payload(self) -> dict[str, object]:
        self.validate()
        return {
            "experiment_id": self.experiment_id,
            "year": self.year,
            "closure_id": self.closure_id,
            "children": [child.canonical_payload() for child in self.children],
            "aggregate_resources_delta": self.aggregate_resources_delta,
            "tolerance": self.tolerance,
        }

    def fingerprint(self) -> str:
        encoded = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def build_incidence_ledger(
    *,
    experiment_id: str,
    year: int,
    closure_class: ClosureClass,
    top_amount: float,
    top_unit: UnitConvention,
    top_recipient_mass: float,
    middle_amount: float,
    middle_unit: UnitConvention,
    middle_recipient_mass: float,
    foreign_transfer_delta: float = 0.0,
    government_absorption_delta: float = 0.0,
    other_household_resource_delta: float = 0.0,
    aggregate_resources_delta: float,
    tolerance: float = DEFAULT_TOLERANCE,
) -> IncidenceLedger:
    """Build a ledger while preserving the originally stated units for each block."""

    return IncidenceLedger(
        experiment_id=experiment_id,
        year=year,
        closure_class=closure_class,
        top=ResourceIncidence.from_amount(
            "top", top_amount, top_unit, top_recipient_mass, tolerance=tolerance
        ),
        middle=ResourceIncidence.from_amount(
            "middle", middle_amount, middle_unit, middle_recipient_mass, tolerance=tolerance
        ),
        foreign_transfer_delta=foreign_transfer_delta,
        government_absorption_delta=government_absorption_delta,
        other_household_resource_delta=other_household_resource_delta,
        aggregate_resources_delta=aggregate_resources_delta,
        tolerance=tolerance,
    )


def build_signed_incidence_receipt(
    *,
    experiment_id: str,
    year: int,
    top_aggregate_delta: float,
    middle_aggregate_delta: float,
    top_recipient_mass: float,
    middle_recipient_mass: float,
    tolerance: float = DEFAULT_TOLERANCE,
) -> IncidenceLedger | CompositeIncidenceReceipt:
    """Build the Amendment-02 receipt for any signed focal synthetic point."""

    for name, value in (
        ("signed top aggregate delta", top_aggregate_delta),
        ("signed middle aggregate delta", middle_aggregate_delta),
        ("signed receipt tolerance", tolerance),
    ):
        _require_finite(name, value)
    if tolerance <= 0.0:
        raise InvariantViolation("signed receipt tolerance must be positive")

    top_zero = _close(top_aggregate_delta, 0.0, tolerance)
    middle_zero = _close(middle_aggregate_delta, 0.0, tolerance)
    if (
        top_aggregate_delta > tolerance
        and middle_aggregate_delta < -tolerance
        and _close(top_aggregate_delta, -middle_aggregate_delta, tolerance)
    ):
        return build_incidence_ledger(
            experiment_id=experiment_id,
            year=year,
            closure_class=ClosureClass.E0_REDISTRIBUTION,
            top_amount=top_aggregate_delta,
            top_unit=UnitConvention.AGGREGATE,
            top_recipient_mass=top_recipient_mass,
            middle_amount=middle_aggregate_delta,
            middle_unit=UnitConvention.AGGREGATE,
            middle_recipient_mass=middle_recipient_mass,
            aggregate_resources_delta=0.0,
            tolerance=tolerance,
        )

    children: list[IncidenceLedger] = []
    if not top_zero:
        top_closure = (
            ClosureClass.D1_RESOURCE_INJECTION
            if top_aggregate_delta > 0.0
            else ClosureClass.D1R_TOP_RESOURCE_WITHDRAWAL
        )
        children.append(
            build_incidence_ledger(
                experiment_id=f"{experiment_id}:top",
                year=year,
                closure_class=top_closure,
                top_amount=top_aggregate_delta,
                top_unit=UnitConvention.AGGREGATE,
                top_recipient_mass=top_recipient_mass,
                middle_amount=0.0,
                middle_unit=UnitConvention.AGGREGATE,
                middle_recipient_mass=middle_recipient_mass,
                aggregate_resources_delta=top_aggregate_delta,
                tolerance=tolerance,
            )
        )
    if not middle_zero:
        middle_closure = (
            ClosureClass.D2_RESOURCE_LOSS
            if middle_aggregate_delta < 0.0
            else ClosureClass.D2R_MIDDLE_RESOURCE_INJECTION
        )
        children.append(
            build_incidence_ledger(
                experiment_id=f"{experiment_id}:middle",
                year=year,
                closure_class=middle_closure,
                top_amount=0.0,
                top_unit=UnitConvention.AGGREGATE,
                top_recipient_mass=top_recipient_mass,
                middle_amount=middle_aggregate_delta,
                middle_unit=UnitConvention.AGGREGATE,
                middle_recipient_mass=middle_recipient_mass,
                aggregate_resources_delta=middle_aggregate_delta,
                tolerance=tolerance,
            )
        )
    if len(children) == 1:
        return children[0]
    return CompositeIncidenceReceipt(
        experiment_id=experiment_id,
        year=year,
        children=tuple(children),
        aggregate_resources_delta=(
            0.0 if top_zero and middle_zero else top_aggregate_delta + middle_aggregate_delta
        ),
        tolerance=tolerance,
    )


def seal_incidence(ledger: IncidenceLedger) -> IncidenceSeal:
    """Create a detached integrity receipt for a currently valid ledger."""

    if not isinstance(ledger, IncidenceLedger):
        raise InvariantViolation("only an IncidenceLedger can be sealed")
    return IncidenceSeal(
        experiment_id=ledger.experiment_id,
        year=ledger.year,
        sha256=ledger.fingerprint(),
    )


def verify_incidence_seal(ledger: IncidenceLedger, seal: IncidenceSeal) -> None:
    """Raise if a ledger is invalid or differs from its detached receipt."""

    if not isinstance(ledger, IncidenceLedger) or not isinstance(seal, IncidenceSeal):
        raise InvariantViolation("incidence integrity verification requires a ledger and seal")
    ledger.validate()
    if ledger.experiment_id != seal.experiment_id or ledger.year != seal.year:
        raise InvariantViolation("incidence ledger identity differs from its integrity seal")
    if not hmac.compare_digest(ledger.fingerprint(), seal.sha256):
        raise InvariantViolation("incidence ledger mutation detected by integrity seal")
