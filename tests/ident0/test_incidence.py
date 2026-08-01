from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys

import pytest

from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.incidence import (
    ClosureClass,
    CompositeIncidenceReceipt,
    IncidenceLedger,
    ResourceIncidence,
    UnitConvention,
    build_incidence_ledger,
    build_signed_incidence_receipt,
    seal_incidence,
    verify_incidence_seal,
)


def _d1() -> IncidenceLedger:
    return build_incidence_ledger(
        experiment_id="d1-2008",
        year=2008,
        closure_class=ClosureClass.D1_RESOURCE_INJECTION,
        top_amount=2.0,
        top_unit=UnitConvention.AGGREGATE,
        top_recipient_mass=0.1,
        middle_amount=0.0,
        middle_unit=UnitConvention.PER_RECIPIENT,
        middle_recipient_mass=0.6,
        aggregate_resources_delta=2.0,
    )


def test_unit_conversion_retains_aggregate_and_per_recipient_values() -> None:
    aggregate = ResourceIncidence.from_amount(
        "top", 2.0, UnitConvention.AGGREGATE, recipient_mass=0.1
    )
    per_recipient = ResourceIncidence.from_amount(
        "middle", -4.0, UnitConvention.PER_RECIPIENT, recipient_mass=0.5
    )

    assert aggregate.aggregate_delta == pytest.approx(2.0)
    assert aggregate.per_recipient_delta == pytest.approx(20.0)
    assert per_recipient.aggregate_delta == pytest.approx(-2.0)
    assert per_recipient.per_recipient_delta == pytest.approx(-4.0)


def test_hand_constructed_unit_mismatch_is_rejected() -> None:
    with pytest.raises(InvariantViolation, match="aggregate/per-recipient"):
        ResourceIncidence(
            recipient_group="top",
            recipient_mass=0.25,
            stated_amount=2.0,
            stated_unit=UnitConvention.AGGREGATE,
            aggregate_delta=2.0,
            per_recipient_delta=2.0,
        )


def test_d1_resource_injection_closes_and_is_not_budget_neutral() -> None:
    ledger = _d1()
    ledger.validate()

    assert ledger.accounting_residual == pytest.approx(0.0)
    assert ledger.top.per_recipient_delta == pytest.approx(20.0)
    assert not ledger.is_budget_neutral


def test_d2_resource_loss_closes_and_is_not_budget_neutral() -> None:
    ledger = build_incidence_ledger(
        experiment_id="d2-2008",
        year=2008,
        closure_class=ClosureClass.D2_RESOURCE_LOSS,
        top_amount=0.0,
        top_unit=UnitConvention.AGGREGATE,
        top_recipient_mass=0.1,
        middle_amount=-4.0,
        middle_unit=UnitConvention.PER_RECIPIENT,
        middle_recipient_mass=0.5,
        aggregate_resources_delta=-2.0,
    )

    assert ledger.middle.aggregate_delta == pytest.approx(-2.0)
    assert ledger.accounting_residual == pytest.approx(0.0)
    assert not ledger.is_budget_neutral


def test_e0_redistribution_requires_equal_and_opposite_aggregate_flows() -> None:
    ledger = build_incidence_ledger(
        experiment_id="e0-2008",
        year=2008,
        closure_class=ClosureClass.E0_REDISTRIBUTION,
        top_amount=10.0,
        top_unit=UnitConvention.PER_RECIPIENT,
        top_recipient_mass=0.1,
        middle_amount=-1.0,
        middle_unit=UnitConvention.AGGREGATE,
        middle_recipient_mass=0.6,
        aggregate_resources_delta=0.0,
    )

    assert ledger.top.aggregate_delta == pytest.approx(1.0)
    assert ledger.middle.aggregate_delta == pytest.approx(-1.0)
    assert ledger.is_budget_neutral


def test_reverse_elementary_and_composite_signed_receipts_close() -> None:
    top_withdrawal = build_signed_incidence_receipt(
        experiment_id="top-reverse",
        year=2010,
        top_aggregate_delta=-0.4,
        middle_aggregate_delta=0.0,
        top_recipient_mass=0.1,
        middle_recipient_mass=0.6,
    )
    middle_injection = build_signed_incidence_receipt(
        experiment_id="middle-reverse",
        year=2010,
        top_aggregate_delta=0.0,
        middle_aggregate_delta=0.7,
        top_recipient_mass=0.1,
        middle_recipient_mass=0.6,
    )
    joint = build_signed_incidence_receipt(
        experiment_id="joint-open",
        year=2010,
        top_aggregate_delta=-0.4,
        middle_aggregate_delta=0.7,
        top_recipient_mass=0.1,
        middle_recipient_mass=0.6,
    )

    assert isinstance(top_withdrawal, IncidenceLedger)
    assert top_withdrawal.closure_class is ClosureClass.D1R_TOP_RESOURCE_WITHDRAWAL
    assert isinstance(middle_injection, IncidenceLedger)
    assert middle_injection.closure_class is ClosureClass.D2R_MIDDLE_RESOURCE_INJECTION
    assert isinstance(joint, CompositeIncidenceReceipt)
    assert joint.closure_id == "C0_COMPOSITE_OPEN"
    assert joint.accounting_residual == pytest.approx(0.0)
    assert joint.aggregate_resources_delta == pytest.approx(0.3)
    assert not joint.is_budget_neutral


def test_signed_receipts_use_e0_only_in_registered_orientation_and_n0_at_zero() -> None:
    e0 = build_signed_incidence_receipt(
        experiment_id="direct-e0",
        year=2011,
        top_aggregate_delta=0.5,
        middle_aggregate_delta=-0.5,
        top_recipient_mass=0.1,
        middle_recipient_mass=0.6,
    )
    reverse = build_signed_incidence_receipt(
        experiment_id="reverse-neutral",
        year=2011,
        top_aggregate_delta=-0.5,
        middle_aggregate_delta=0.5,
        top_recipient_mass=0.1,
        middle_recipient_mass=0.6,
    )
    zero = build_signed_incidence_receipt(
        experiment_id="zero",
        year=2011,
        top_aggregate_delta=0.0,
        middle_aggregate_delta=0.0,
        top_recipient_mass=0.1,
        middle_recipient_mass=0.6,
    )

    assert e0.closure_class is ClosureClass.E0_REDISTRIBUTION
    assert isinstance(reverse, CompositeIncidenceReceipt)
    assert reverse.is_budget_neutral
    assert reverse.closure_id == "C0_COMPOSITE_OPEN"
    assert isinstance(zero, CompositeIncidenceReceipt)
    assert zero.closure_id == "N0_NO_CHANGE"
    assert zero.fingerprint()


def test_unbalanced_redistribution_mutation_is_rejected() -> None:
    with pytest.raises(InvariantViolation, match="equal and opposite"):
        build_incidence_ledger(
            experiment_id="bad-e0",
            year=2008,
            closure_class=ClosureClass.E0_REDISTRIBUTION,
            top_amount=1.0,
            top_unit=UnitConvention.AGGREGATE,
            top_recipient_mass=0.1,
            middle_amount=-0.8,
            middle_unit=UnitConvention.AGGREGATE,
            middle_recipient_mass=0.6,
            aggregate_resources_delta=0.2,
        )


def test_per_recipient_amount_mislabeled_as_aggregate_breaks_declared_closure() -> None:
    with pytest.raises(InvariantViolation, match="accounting does not close"):
        build_incidence_ledger(
            experiment_id="unit-mutation",
            year=2008,
            closure_class=ClosureClass.D1_RESOURCE_INJECTION,
            top_amount=10.0,
            top_unit=UnitConvention.AGGREGATE,
            top_recipient_mass=0.1,
            middle_amount=0.0,
            middle_unit=UnitConvention.AGGREGATE,
            middle_recipient_mass=0.6,
            # The preregistered aggregate change is 0.1 * 10 = 1.
            aggregate_resources_delta=1.0,
        )


def test_closure_label_mutation_is_rejected() -> None:
    with pytest.raises(InvariantViolation, match="E0 requires"):
        replace(_d1(), closure_class=ClosureClass.E0_REDISTRIBUTION)


def test_block_cannot_weaken_the_ledger_tolerance() -> None:
    ledger = _d1()
    lax_top = replace(ledger.top, tolerance=1e-3)

    with pytest.raises(InvariantViolation, match="same tolerance"):
        replace(ledger, top=lax_top)


def test_detached_seal_detects_otherwise_valid_mutation() -> None:
    ledger = _d1()
    seal = seal_incidence(ledger)
    mutated = replace(ledger, experiment_id="different-valid-experiment")

    with pytest.raises(InvariantViolation, match="identity differs"):
        verify_incidence_seal(mutated, seal)


def test_revalidation_detects_in_memory_numeric_mutation() -> None:
    ledger = _d1()
    object.__setattr__(ledger.top, "aggregate_delta", 999.0)

    with pytest.raises(InvariantViolation, match="aggregate/per-recipient"):
        ledger.validate()


def test_failure_gates_remain_active_under_optimized_python() -> None:
    source_root = Path(__file__).resolve().parents[2] / "src"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(source_root), environment.get("PYTHONPATH", "")]
    )
    script = """
from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.incidence import ResourceIncidence, UnitConvention
try:
    ResourceIncidence(
        recipient_group='top', recipient_mass=0.1, stated_amount=1.0,
        stated_unit=UnitConvention.AGGREGATE, aggregate_delta=1.0,
        per_recipient_delta=1.0,
    )
except InvariantViolation:
    raise SystemExit(0)
raise SystemExit(9)
"""
    result = subprocess.run(
        [sys.executable, "-O", "-c", script],
        check=False,
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
