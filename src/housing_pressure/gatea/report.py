"""Deterministic, non-overwriting artifacts for the public Gate A run."""

from __future__ import annotations

import csv
from datetime import date, datetime
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from housing_pressure.ident0.errors import InvariantViolation
from housing_pressure.ident0.manifest import sha256_file

from .extract import DerivedTable, GateAResult
from .fetch import SourceReceipt


def _write_bytes_new(path: Path, payload: bytes) -> None:
    if path.exists():
        raise InvariantViolation(f"refusing to overwrite Gate A artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    if temporary.exists():
        raise InvariantViolation(f"temporary Gate A artifact already exists: {temporary}")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _json_default(value: object) -> object:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"cannot serialize {type(value).__name__} to Gate A JSON")


def write_json_new(path: Path, payload: object) -> str:
    """Write canonical human-readable JSON and return its SHA-256."""

    encoded = (
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
            default=_json_default,
        )
        + "\n"
    ).encode("utf-8")
    _write_bytes_new(path, encoded)
    return hashlib.sha256(encoded).hexdigest()


def _csv_value(value: object) -> object:
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvariantViolation("derived CSV contains a non-finite float")
        return format(value, ".17g")
    if isinstance(value, (str, int)):
        return value
    raise InvariantViolation(f"unsupported derived CSV value: {type(value).__name__}")


def write_derived_tables(tables: Sequence[DerivedTable], directory: Path) -> tuple[Path, ...]:
    """Write the validated tables with stable field and float serialization."""

    if len({table.filename for table in tables}) != len(tables):
        raise InvariantViolation("derived Gate A table filenames must be unique")
    paths: list[Path] = []
    for table in tables:
        if Path(table.filename).name != table.filename or not table.filename.endswith(".csv"):
            raise InvariantViolation(f"unsafe derived table filename: {table.filename}")
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream,
            fieldnames=table.fieldnames,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in table.rows:
            writer.writerow({name: _csv_value(row[name]) for name in table.fieldnames})
        path = directory / table.filename
        _write_bytes_new(path, stream.getvalue().encode("utf-8"))
        paths.append(path)
    return tuple(paths)


def table_metadata(tables: Sequence[DerivedTable], directory: Path) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "tables": [
            {
                "filename": table.filename,
                "sha256": sha256_file(directory / table.filename),
                "rows": len(table.rows),
                "fields": list(table.fieldnames),
                "source_ids": list(table.source_ids),
                "description": table.description,
            }
            for table in tables
        ],
    }


def source_receipt_payload(receipts: Sequence[SourceReceipt]) -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "all_hashes_matched": True,
        "sources": [receipt.to_dict() for receipt in receipts],
        "assurance": (
            "A matching digest establishes byte identity with the preregistered download, "
            "not substantive validity or causal identification."
        ),
    }


def _format_value(value: object, field: str | None = None) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if field in {"base_index", "end_index"}:
            return f"{value:.1f}"
        if field and (
            field.endswith(("_pct", "_pp", "_change_pp", "_pct_change"))
            or field in {"endpoint_100_log_change", "mean_spread_pp"}
        ):
            return f"{value:.4f}"
        return f"{value:.8g}"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return ", ".join(_format_value(item) for item in value)
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown_report(
    result: GateAResult,
    receipts: Sequence[SourceReceipt],
    *,
    manifest_sha256: str,
) -> str:
    """Render a compact report whose wording preserves the claim ceiling."""

    lines = [
        "# Public Gate A accounting report",
        "",
        f"**Decision:** `{result.decision}`  ",
        f"**Full Gate A authorized:** `{str(result.full_gate_a_authorized).lower()}`  ",
        f"**Protocol:** `{result.protocol_version}`  ",
        f"**Core period:** {result.core_period}  ",
        f"**Run manifest SHA-256:** `{manifest_sha256}`",
        "",
        "The hash-pinned open subset reproduced the declared accounting paths. This is not "
        "a pass of the full evidence gate and does not identify a top-resource contribution.",
        "",
        "## Accounting facts",
        "",
    ]
    for fact_id, values in result.facts.items():
        lines.extend((f"### {fact_id}", "", "| Field | Value |", "|---|---|"))
        if not isinstance(values, Mapping):
            lines.append(f"| value | {_format_value(values)} |")
        else:
            for key, value in values.items():
                lines.append(f"| {key} | {_format_value(value, key)} |")
        lines.append("")

    lines.extend(("## Validation checks", "", "| Check | Status | Expected |", "|---|---:|---|"))
    for check in result.checks:
        lines.append(f"| {check.name} | {check.status} | {_format_value(check.expected)} |")

    lines.extend(
        ("", "## Source receipts", "", "| Source | Mode | Bytes | SHA-256 |", "|---|---|---:|---|")
    )
    for receipt in receipts:
        lines.append(
            f"| {receipt.source_id} | {receipt.retrieval_mode} | {receipt.bytes} | "
            f"`{receipt.sha256}` |"
        )

    lines.extend(("", "## Outputs still blocked", "", "| Output | Reason |", "|---|---|"))
    for output_id, reason in result.blocked_outputs.items():
        lines.append(f"| {output_id} | {_format_value(reason)} |")

    lines.extend(("", "## Assurance boundary", ""))
    lines.extend(f"- {item}" for item in result.assurance_boundary)
    lines.extend(
        (
            "",
            "The EHS endpoint values and the 2015–2019 HPI/PIPR relative-index change were "
            "observed during feasibility work. Their appearance here is a source and arithmetic "
            "reproduction, not untouched confirmation.",
            "",
        )
    )
    return "\n".join(lines)


def write_markdown_new(path: Path, text: str) -> str:
    encoded = text.encode("utf-8")
    _write_bytes_new(path, encoded)
    return hashlib.sha256(encoded).hexdigest()


def write_artifact_manifest(output: Path, files: Iterable[Path]) -> tuple[Path, str]:
    """Bind every listed artifact by relative path without recursively hashing itself."""

    resolved_output = output.resolve()
    entries: list[tuple[str, str]] = []
    for path in sorted({item.resolve() for item in files}, key=str):
        if not path.is_file():
            raise InvariantViolation(f"artifact manifest input is not a file: {path}")
        try:
            relative = path.relative_to(resolved_output).as_posix()
        except ValueError as exc:
            raise InvariantViolation(f"artifact is outside Gate A output: {path}") from exc
        entries.append((relative, sha256_file(path)))
    target = resolved_output / "ARTIFACT_MANIFEST.sha256"
    text = "".join(f"{digest}  {relative}\n" for relative, digest in entries)
    digest = write_markdown_new(target, text)
    return target, digest


__all__ = [
    "render_markdown_report",
    "source_receipt_payload",
    "table_metadata",
    "write_artifact_manifest",
    "write_derived_tables",
    "write_json_new",
    "write_markdown_new",
]
