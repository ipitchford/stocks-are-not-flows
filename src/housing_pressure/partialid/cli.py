"""Manifest-bound command for the post-IDENT-0 design-geometry certificate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from housing_pressure.ident0.diagnostics import load_config
from housing_pressure.ident0.errors import InvariantViolation as ManifestInvariantViolation
from housing_pressure.ident0.manifest import build_manifest, sha256_file, write_manifest

from .design_audit import HousingDesignAudit, build_housing_design_audit
from .errors import InvariantViolation


def _repository_from_source() -> Path:
    return Path(__file__).resolve().parents[3]


def _parser(repository: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="housing-partialid",
        description=(
            "Certify the synthetic focal-versus-rival design geometry after FAIL-IDENT-0. "
            "This command cannot emit an empirical England bound."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=repository / "configs" / "ident0.json",
        help="validated IDENT-0 configuration",
    )
    parser.add_argument(
        "--ident0-report",
        type=Path,
        default=(repository / "results" / "ident0" / "20260801-ident0-failfast-v2" / "REPORT.json"),
        help="authoritative FAIL-IDENT-0 report",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="new directory for manifest-bound certificate artifacts",
    )
    return parser


def _manifest_inputs(
    repository: Path, config_path: Path, ident0_report_path: Path
) -> tuple[Path, ...]:
    partialid = tuple(sorted((repository / "src" / "housing_pressure" / "partialid").glob("*.py")))
    ident0 = tuple(
        repository / "src" / "housing_pressure" / "ident0" / name
        for name in (
            "diagnostics.py",
            "errors.py",
            "manifest.py",
            "measurement.py",
            "measurement_bridge.py",
            "observation_adapter.py",
            "response_model.py",
            "rivals.py",
            "timing.py",
        )
    )
    fixed = (
        config_path,
        ident0_report_path,
        repository / "pyproject.toml",
        repository / "uv.lock",
        repository / "docs" / "identification" / "PARTIAL_IDENTIFICATION_PROTOCOL.md",
        repository / "docs" / "model" / "CLAIM_LEDGER.md",
        repository / "docs" / "provenance" / "STAGE1_DECISION.md",
    )
    return tuple(dict.fromkeys((*partialid, *ident0, *fixed)))


def _read_ident0_report(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InvariantViolation(f"cannot read authoritative IDENT-0 report: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InvariantViolation(f"authoritative IDENT-0 report is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvariantViolation("authoritative IDENT-0 report root must be an object")
    checksum_path = path.with_name("REPORT.sha256")
    if checksum_path.is_file():
        fields = checksum_path.read_text(encoding="utf-8").strip().split()
        if len(fields) != 2 or fields[1] != "REPORT.json" or fields[0] != sha256_file(path):
            raise InvariantViolation("authoritative IDENT-0 report checksum does not match")
    return payload


def _write_new(path: Path, payload: bytes) -> str:
    if path.exists():
        raise InvariantViolation(f"refusing to overwrite partial-ID artifact: {path}")
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        raise InvariantViolation(f"temporary partial-ID artifact exists: {temporary}")
    temporary.write_bytes(payload)
    temporary.replace(path)
    return hashlib.sha256(payload).hexdigest()


def _render_markdown(report: HousingDesignAudit, manifest_sha256: str) -> str:
    raw = report.public_unit_geometry
    scaled = report.scaled_geometry
    lines = [
        "# Post-IDENT-0 design-geometry certificate",
        "",
        f"**Decision:** `{report.decision}`  ",
        "**Unique attribution authorized:** `false`  ",
        "**Empirical England bound:** `false`  ",
        f"**Run manifest SHA-256:** `{manifest_sha256}`",
        "",
        "The maintained seven-column design is locally full rank, but after the four "
        "deliberately constructed rivals are admitted the 57-by-11 matrix has rank 9. "
        "The focal `z_top` column lies in the span of the other maintained and rival "
        "columns at the declared numerical tolerance.",
        "",
        "| Basis | Maintained rank | Augmented rank | Focal relative residual | In span |",
        "|---|---:|---:|---:|---:|",
        (
            f"| Public units | {report.maintained_public_unit.rank}/7 | "
            f"{report.augmented_public_unit.rank}/11 | {raw.relative_residual_norm:.6g} | "
            f"{str(raw.focal_in_nuisance_span).lower()} |"
        ),
        (
            f"| Synthetic diagonal scaling | {report.maintained_scaled.rank}/7 | "
            f"{report.augmented_scaled.rank}/11 | {scaled.relative_residual_norm:.6g} | "
            f"{str(scaled.focal_in_nuisance_span).lower()} |"
        ),
        "",
        "## Assurance boundary",
        "",
        *(f"- {item}" for item in report.assurance_boundary),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    repository = _repository_from_source()
    arguments = _parser(repository).parse_args(argv)
    config_path = arguments.config.resolve()
    ident0_report_path = arguments.ident0_report.resolve()
    output = arguments.output_dir.resolve()
    if output.exists():
        raise InvariantViolation(f"partial-ID output directory already exists: {output}")
    if not output.parent.is_dir():
        raise InvariantViolation(f"partial-ID output parent does not exist: {output.parent}")

    config = load_config(config_path)
    ident0_report = _read_ident0_report(ident0_report_path)
    command = tuple(sys.argv if argv is None else ("housing-partialid", *argv))
    try:
        manifest = build_manifest(
            repository,
            _manifest_inputs(repository, config_path, ident0_report_path),
            seed=config.seed,
            command=command,
            require_clean=True,
        )
    except ManifestInvariantViolation as exc:
        raise InvariantViolation(str(exc)) from exc

    report = build_housing_design_audit(
        config,
        ident0_report,
        authoritative_ident0_report_sha256=sha256_file(ident0_report_path),
    )
    output.mkdir(parents=False, exist_ok=False)
    manifest_path = output / "MANIFEST.json"
    write_manifest(manifest, manifest_path)
    manifest_digest = sha256_file(manifest_path)
    report_payload = report.to_dict()
    report_payload["manifest_sha256"] = manifest_digest
    encoded = (json.dumps(report_payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    report_digest = _write_new(output / "REPORT.json", encoded)
    _write_new(output / "REPORT.sha256", f"{report_digest}  REPORT.json\n".encode())
    _write_new(output / "REPORT.md", _render_markdown(report, manifest_digest).encode())
    print(
        json.dumps(
            {
                "decision": report.decision,
                "empirical_england_bound": False,
                "report_sha256": report_digest,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
