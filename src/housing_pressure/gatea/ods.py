"""Minimal, bounded ODS reader for official live tables.

The official spreadsheets used here contain plain rectangular tables.  A small
reader keeps the runtime boundary auditable and preserves publisher numeric
strings; it is not intended to implement the full OpenDocument standard.
"""

from __future__ import annotations

import io
from types import MappingProxyType
from typing import Mapping
import xml.etree.ElementTree as ET
import zipfile

from housing_pressure.ident0.errors import InvariantViolation


_NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
}
_MAX_ARCHIVE_MEMBERS = 128
_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
_MAX_ROWS_PER_SHEET = 100_000
_MAX_COLUMNS_PER_ROW = 2_000
_MAX_REPEAT = 100_000
_MAX_DECLARED_REPEAT = 10_000_000


def _attribute(namespace: str, name: str) -> str:
    return f"{{{_NS[namespace]}}}{name}"


def _positive_repeat(raw: str | None, label: str, *, materialized: bool = True) -> int:
    try:
        value = 1 if raw is None else int(raw)
    except ValueError as exc:
        raise InvariantViolation(f"ODS {label} is not an integer") from exc
    maximum = _MAX_REPEAT if materialized else _MAX_DECLARED_REPEAT
    if not 1 <= value <= maximum:
        raise InvariantViolation(f"ODS {label} is outside the safe range")
    return value


def _cell_value(cell: ET.Element) -> str:
    paragraphs = cell.findall(".//text:p", _NS)
    text = " ".join("".join(item.itertext()) for item in paragraphs).strip()
    return cell.attrib.get(_attribute("office", "value"), text)


def read_ods_tables(payload: bytes) -> Mapping[str, tuple[tuple[str, ...], ...]]:
    """Return sheet names mapped to immutable rows of publisher strings."""

    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except zipfile.BadZipFile as exc:
        raise InvariantViolation("ODS payload is not a valid ZIP archive") from exc
    with archive:
        members = archive.infolist()
        if len(members) > _MAX_ARCHIVE_MEMBERS:
            raise InvariantViolation("ODS archive has too many members")
        if sum(item.file_size for item in members) > _MAX_UNCOMPRESSED_BYTES:
            raise InvariantViolation("ODS archive expands beyond the safety limit")
        names = {item.filename for item in members}
        if "content.xml" not in names or "mimetype" not in names:
            raise InvariantViolation("ODS archive is missing content.xml or mimetype")
        mimetype = archive.read("mimetype")
        if mimetype != b"application/vnd.oasis.opendocument.spreadsheet":
            raise InvariantViolation("ODS mimetype is not a spreadsheet")
        try:
            root = ET.fromstring(archive.read("content.xml"))
        except ET.ParseError as exc:
            raise InvariantViolation("ODS content.xml is malformed") from exc

    result: dict[str, tuple[tuple[str, ...], ...]] = {}
    for table in root.findall(".//table:table", _NS):
        name = table.attrib.get(_attribute("table", "name"), "")
        if not name or name in result:
            raise InvariantViolation("ODS sheet names must be non-empty and unique")
        rows: list[tuple[str, ...]] = []
        for row in table.findall("table:table-row", _NS):
            cells = [
                cell
                for cell in list(row)
                if cell.tag
                in {
                    _attribute("table", "table-cell"),
                    _attribute("table", "covered-table-cell"),
                }
            ]
            cell_values = [_cell_value(cell) for cell in cells]
            nonempty = [index for index, value in enumerate(cell_values) if value]
            if not nonempty:
                _positive_repeat(
                    row.attrib.get(_attribute("table", "number-rows-repeated")),
                    "omitted blank-row repeat",
                    materialized=False,
                )
                continue
            last_nonempty = nonempty[-1]
            row_repeat = _positive_repeat(
                row.attrib.get(_attribute("table", "number-rows-repeated")),
                "row repeat",
            )
            values: list[str] = []
            for index, (cell, value) in enumerate(zip(cells, cell_values)):
                column_repeat = _positive_repeat(
                    cell.attrib.get(_attribute("table", "number-columns-repeated")),
                    "column repeat" if index <= last_nonempty else "omitted blank-column repeat",
                    materialized=index <= last_nonempty,
                )
                if index > last_nonempty:
                    continue
                if len(values) + column_repeat > _MAX_COLUMNS_PER_ROW:
                    raise InvariantViolation("ODS row exceeds the safe column limit")
                values.extend([value] * column_repeat)
            if len(rows) + row_repeat > _MAX_ROWS_PER_SHEET:
                raise InvariantViolation("ODS sheet exceeds the safe row limit")
            frozen = tuple(values)
            rows.extend([frozen] * row_repeat)
        result[name] = tuple(rows)
    if not result:
        raise InvariantViolation("ODS workbook contains no sheets")
    return MappingProxyType(result)


__all__ = ["read_ods_tables"]
