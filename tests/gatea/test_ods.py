from __future__ import annotations

import io
import zipfile

import pytest

from housing_pressure.gatea.ods import read_ods_tables
from housing_pressure.ident0.errors import InvariantViolation


MIMETYPE = b"application/vnd.oasis.opendocument.spreadsheet"


def _ods(content: str, *, mimetype: bytes = MIMETYPE) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("mimetype", mimetype, compress_type=zipfile.ZIP_STORED)
        archive.writestr("content.xml", content)
    return output.getvalue()


def test_minimal_ods_reader_preserves_values_and_repeats() -> None:
    payload = _ods(
        """<?xml version="1.0" encoding="UTF-8"?>
        <office:document-content
          xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
          xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
          xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
          <office:body><office:spreadsheet>
            <table:table table:name="Sheet 1">
              <table:table-row>
                <table:table-cell><text:p>label</text:p></table:table-cell>
                <table:table-cell office:value="1.25"><text:p>1.25</text:p></table:table-cell>
                <table:table-cell table:number-columns-repeated="3"/>
              </table:table-row>
              <table:table-row table:number-rows-repeated="2">
                <table:table-cell><text:p>repeat</text:p></table:table-cell>
              </table:table-row>
            </table:table>
          </office:spreadsheet></office:body>
        </office:document-content>"""
    )
    tables = read_ods_tables(payload)
    assert tables["Sheet 1"] == (("label", "1.25"), ("repeat",), ("repeat",))


def test_large_terminal_blank_repeats_are_not_materialized() -> None:
    payload = _ods(
        """<office:document-content
          xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
          xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
          xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
          <office:body><office:spreadsheet><table:table table:name="S">
          <table:table-row><table:table-cell><text:p>kept</text:p></table:table-cell>
          <table:table-cell table:number-columns-repeated="16375"/></table:table-row>
          <table:table-row table:number-rows-repeated="1048533"><table:table-cell/></table:table-row>
          </table:table></office:spreadsheet></office:body></office:document-content>"""
    )
    assert read_ods_tables(payload)["S"] == (("kept",),)


def test_bad_mimetype_and_oversized_repeat_fail_closed() -> None:
    content = """<office:document-content
      xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
      xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0"
      xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">
      <office:body><office:spreadsheet><table:table table:name="S">
      <table:table-row><table:table-cell table:number-columns-repeated="2001"/>
      <table:table-cell><text:p>kept</text:p></table:table-cell></table:table-row>
      </table:table></office:spreadsheet></office:body></office:document-content>"""
    with pytest.raises(InvariantViolation, match="mimetype"):
        read_ods_tables(_ods(content, mimetype=b"text/plain"))
    with pytest.raises(InvariantViolation, match="column limit"):
        read_ods_tables(_ods(content))
