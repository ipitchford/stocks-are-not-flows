from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from housing_pressure.ident0.diagnostics import load_config
from housing_pressure.partialid import InvariantViolation, build_housing_design_audit


REPOSITORY = Path(__file__).resolve().parents[2]
IDENT0_REPORT = REPOSITORY / "results" / "ident0" / "20260801-ident0-failfast-v2" / "REPORT.json"


def _report() -> tuple[dict[str, object], str]:
    payload = IDENT0_REPORT.read_bytes()
    return json.loads(payload), hashlib.sha256(payload).hexdigest()


def test_housing_design_audit_certifies_rank_without_empirical_promotion() -> None:
    report, digest = _report()
    result = build_housing_design_audit(
        load_config(REPOSITORY / "configs" / "ident0.json"),
        report,
        authoritative_ident0_report_sha256=digest,
    )

    assert result.decision == "STOP-UNIQUE+GO-PARTIAL-ID-THEORY"
    assert not result.pass_unique_attribution_authorized
    assert not result.empirical_england_bound
    assert result.target_observations == 57
    assert result.maintained_public_unit.rank == 7
    assert result.augmented_public_unit.rank == 9
    assert result.maintained_scaled.rank == 7
    assert result.augmented_scaled.rank == 9
    assert result.public_unit_geometry.focal_in_nuisance_span
    assert result.scaled_geometry.focal_in_nuisance_span
    assert result.public_unit_geometry.dual_discriminator is None
    assert result.public_unit_derivative_control_max_abs <= 1e-7
    json.dumps(result.to_dict(), allow_nan=False)


def test_design_audit_requires_authoritative_failed_gate() -> None:
    report, digest = _report()
    report["decision"] = "CONTINUE-TO-FULL-GATE"
    with pytest.raises(InvariantViolation, match="FAIL-IDENT-0"):
        build_housing_design_audit(
            load_config(REPOSITORY / "configs" / "ident0.json"),
            report,
            authoritative_ident0_report_sha256=digest,
        )
