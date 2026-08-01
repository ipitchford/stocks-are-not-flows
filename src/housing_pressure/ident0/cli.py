"""Command-line entry point for the manifest-bound IDENT-0 fail-fast run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .diagnostics import load_config
from .errors import InvariantViolation
from .gate_runner import run_fail_fast_gate
from .manifest import build_manifest, write_manifest


def _repository_from_source() -> Path:
    return Path(__file__).resolve().parents[3]


def _parser(repository: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="housing-ident0",
        description=(
            "Run the manifest-bound IDENT-0 fail-fast front. This command cannot emit "
            "PASS-IDENT-0; it emits FAIL-IDENT-0 or CONTINUE-TO-FULL-GATE."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=repository / "configs" / "ident0.json",
        help="validated IDENT-0 JSON configuration",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="new directory for MANIFEST.json, REPORT.json, and REPORT.sha256",
    )
    parser.add_argument(
        "--exit-zero-on-scientific-fail",
        action="store_true",
        help="write a failing scientific report but return shell status zero",
    )
    return parser


def _manifest_inputs(repository: Path, config: Path) -> tuple[Path, ...]:
    sources = tuple(sorted((repository / "src" / "housing_pressure" / "ident0").glob("*.py")))
    fixed = (
        config.resolve(),
        repository / "pyproject.toml",
        repository / "uv.lock",
        repository / "docs" / "identification" / "IDENT0_PROTOCOL.md",
        repository / "docs" / "model" / "CLAIM_LEDGER.md",
        repository / "docs" / "provenance" / "STAGE1_DECISION.md",
    )
    return tuple(dict.fromkeys((*sources, *fixed)))


def _write_report(payload: dict[str, object], destination: Path) -> str:
    if destination.exists():
        raise InvariantViolation(f"report already exists: {destination}")
    encoded = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode(
        "utf-8"
    )
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_bytes(encoded)
    temporary.replace(destination)
    return hashlib.sha256(encoded).hexdigest()


def main(argv: list[str] | None = None) -> int:
    repository = _repository_from_source()
    arguments = _parser(repository).parse_args(argv)
    output = arguments.output_dir.resolve()
    if output.exists():
        raise InvariantViolation(f"output directory already exists: {output}")
    output.mkdir(parents=True, exist_ok=False)

    config_path = arguments.config.resolve()
    config = load_config(config_path)
    command = tuple(sys.argv if argv is None else ("housing-ident0", *argv))
    manifest = build_manifest(
        repository,
        _manifest_inputs(repository, config_path),
        seed=config.seed,
        command=command,
        require_clean=True,
    )
    write_manifest(manifest, output / "MANIFEST.json")

    report = run_fail_fast_gate(config)
    report_path = output / "REPORT.json"
    digest = _write_report(report.to_dict(), report_path)
    (output / "REPORT.sha256").write_text(f"{digest}  REPORT.json\n", encoding="utf-8")
    print(json.dumps({"decision": report.decision, "report_sha256": digest}, sort_keys=True))
    if report.decision == "FAIL-IDENT-0" and not arguments.exit_zero_on_scientific_fail:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
