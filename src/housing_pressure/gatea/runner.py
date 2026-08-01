"""Manifest-bound execution of the licence-safe public Gate A subset."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable

from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.manifest import build_manifest, sha256_file, write_manifest

from .config import GateAConfig, load_config
from .extract import extract_open_accounting
from .fetch import SourceReceipt, retrieve_source
from .plotting import create_figures
from .report import (
    render_markdown_report,
    source_receipt_payload,
    table_metadata,
    write_artifact_manifest,
    write_derived_tables,
    write_json_new,
    write_markdown_new,
)


@dataclass(frozen=True, slots=True)
class GateARunReceipt:
    decision: str
    full_gate_a_authorized: bool
    output_directory: str
    report_sha256: str
    artifact_manifest_sha256: str
    source_count: int
    figure_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "full_gate_a_authorized": self.full_gate_a_authorized,
            "output_directory": self.output_directory,
            "report_sha256": self.report_sha256,
            "artifact_manifest_sha256": self.artifact_manifest_sha256,
            "source_count": self.source_count,
            "figure_count": self.figure_count,
        }


def _manifest_inputs(repository: Path, config_path: Path) -> tuple[Path, ...]:
    sources = tuple(sorted((repository / "src" / "housing_pressure" / "gatea").glob("*.py")))
    fixed = (
        config_path.resolve(),
        repository / "pyproject.toml",
        repository / "uv.lock",
        repository / "docs" / "data" / "PUBLIC_GATE_A_PROTOCOL.md",
        repository / "docs" / "model" / "CLAIM_LEDGER.md",
        repository / "docs" / "provenance" / "STAGE1_DECISION.md",
    )
    return tuple(dict.fromkeys((*sources, *fixed)))


def _validate_output(output: Path) -> None:
    if output.exists():
        raise InvariantViolation(f"Gate A output directory already exists: {output}")
    parent = output.parent.resolve()
    if not parent.is_dir():
        raise InvariantViolation(f"Gate A output parent does not exist: {parent}")


def run_public_gate_a(
    *,
    repository: Path,
    config_path: Path,
    output_directory: Path,
    command: Iterable[str],
    offline_source_directory: Path | None = None,
    make_plots: bool = True,
) -> GateARunReceipt:
    """Run the open subset; this function can never authorize the full Gate A."""

    repository = repository.resolve()
    config_path = config_path.resolve()
    output = output_directory.resolve()
    _validate_output(output)
    config: GateAConfig = load_config(config_path)
    manifest = build_manifest(
        repository,
        _manifest_inputs(repository, config_path),
        seed=config.seed,
        command=command,
        require_clean=True,
    )

    output.mkdir(parents=False, exist_ok=False)
    manifest_path = output / "MANIFEST.json"
    write_manifest(manifest, manifest_path)

    raw_directory = output / "raw"
    payloads: dict[str, bytes] = {}
    receipts: list[SourceReceipt] = []
    raw_paths: list[Path] = []
    for source in config.sources:
        retrieved = retrieve_source(
            source,
            raw_directory,
            user_agent=config.user_agent,
            offline_source_directory=offline_source_directory,
        )
        payloads[source.source_id] = retrieved.path.read_bytes()
        receipts.append(retrieved.receipt)
        raw_paths.append(retrieved.path)

    result = extract_open_accounting(config, payloads)
    if result.full_gate_a_authorized:
        raise InvariantViolation("public Gate A runner is forbidden from authorizing the full gate")

    derived_directory = output / "derived"
    derived_paths = write_derived_tables(result.tables, derived_directory)
    table_metadata_path = output / "TABLE_METADATA.json"
    write_json_new(table_metadata_path, table_metadata(result.tables, derived_directory))

    source_receipts_path = output / "SOURCE_RECEIPTS.json"
    write_json_new(source_receipts_path, source_receipt_payload(receipts))

    figure_paths: tuple[Path, ...] = ()
    if make_plots:
        figure_paths = create_figures(result.tables, output / "figures")

    manifest_digest = sha256_file(manifest_path)
    report_payload = result.report_dict()
    report_payload["manifest_sha256"] = manifest_digest
    report_payload["source_receipts_file"] = source_receipts_path.name
    report_payload["table_metadata_file"] = table_metadata_path.name
    report_payload["figure_files"] = [path.relative_to(output).as_posix() for path in figure_paths]
    report_path = output / "REPORT.json"
    report_digest = write_json_new(report_path, report_payload)
    report_sha_path = output / "REPORT.sha256"
    write_markdown_new(report_sha_path, f"{report_digest}  REPORT.json\n")
    markdown_path = output / "REPORT.md"
    write_markdown_new(
        markdown_path,
        render_markdown_report(result, receipts, manifest_sha256=manifest_digest),
    )

    bound_files = (
        manifest_path,
        source_receipts_path,
        table_metadata_path,
        report_path,
        report_sha_path,
        markdown_path,
        *raw_paths,
        *derived_paths,
        *figure_paths,
    )
    artifact_manifest_path, artifact_manifest_digest = write_artifact_manifest(output, bound_files)
    if hashlib.sha256(artifact_manifest_path.read_bytes()).hexdigest() != artifact_manifest_digest:
        raise InvariantViolation("artifact manifest self-digest mismatch")
    return GateARunReceipt(
        decision=result.decision,
        full_gate_a_authorized=result.full_gate_a_authorized,
        output_directory=output.as_posix(),
        report_sha256=report_digest,
        artifact_manifest_sha256=artifact_manifest_digest,
        source_count=len(receipts),
        figure_count=len(figure_paths),
    )


__all__ = ["GateARunReceipt", "run_public_gate_a"]
