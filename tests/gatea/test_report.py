from __future__ import annotations

from datetime import date
from pathlib import Path
from types import MappingProxyType

import pytest

from housing_pressure.gatea.extract import DerivedTable
from housing_pressure.gatea.report import (
    table_metadata,
    write_artifact_manifest,
    write_derived_tables,
)
from housing_pressure.ident0.errors import InvariantViolation


def _table() -> DerivedTable:
    return DerivedTable(
        filename="example.csv",
        fieldnames=("date", "value", "missing"),
        rows=(MappingProxyType({"date": date(2020, 1, 1), "value": 1.0 / 3.0, "missing": None}),),
        source_ids=("TEST",),
        description="test table",
    )


def test_table_serialization_and_hash_manifest(tmp_path: Path) -> None:
    derived = tmp_path / "derived"
    paths = write_derived_tables((_table(),), derived)
    assert paths[0].read_text(encoding="utf-8") == (
        "date,value,missing\n2020-01-01,0.33333333333333331,\n"
    )
    metadata = table_metadata((_table(),), derived)
    assert metadata["tables"][0]["rows"] == 1
    manifest, digest = write_artifact_manifest(tmp_path, paths)
    assert len(digest) == 64
    assert "derived/example.csv" in manifest.read_text(encoding="utf-8")


def test_table_writer_refuses_overwrite(tmp_path: Path) -> None:
    write_derived_tables((_table(),), tmp_path)
    with pytest.raises(InvariantViolation, match="refusing to overwrite"):
        write_derived_tables((_table(),), tmp_path)
