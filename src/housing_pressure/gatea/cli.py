"""Command-line entry point for the public Gate A accounting run."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .runner import run_public_gate_a


def _repository_from_source() -> Path:
    return Path(__file__).resolve().parents[3]


def _parser(repository: Path) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="housing-gatea",
        description=(
            "Reproduce the hash-pinned licence-safe public accounting subset. "
            "This command cannot authorize full Gate A or structural estimation."
        ),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=repository / "configs" / "gatea_public.json",
        help="strict public Gate A JSON configuration",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="new directory for sources, derived tables, figures, and reports",
    )
    parser.add_argument(
        "--offline-source-dir",
        type=Path,
        help="copy exact hash-matching files from this directory instead of HTTPS",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="omit descriptive PDF/SVG figures (accounting extraction is unchanged)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    repository = _repository_from_source()
    arguments = _parser(repository).parse_args(argv)
    command = tuple(sys.argv if argv is None else ("housing-gatea", *argv))
    receipt = run_public_gate_a(
        repository=repository,
        config_path=arguments.config,
        output_directory=arguments.output_dir,
        command=command,
        offline_source_directory=arguments.offline_source_dir,
        make_plots=not arguments.no_plots,
    )
    print(json.dumps(receipt.to_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
