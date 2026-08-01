from __future__ import annotations

import hashlib
import html
import io
from types import MappingProxyType
import zipfile

import pytest

from housing_pressure.gatea import extract as extraction
from housing_pressure.gatea.config import GateAConfig, SourceSpec
from housing_pressure.gatea.extract import validate_payload_set
from housing_pressure.ident0.errors import InvariantViolation


def _cell(value: object) -> str:
    text = html.escape(str(value))
    return f"<table:table-cell><text:p>{text}</text:p></table:table-cell>"


def _row(*values: object) -> str:
    return "<table:table-row>" + "".join(_cell(value) for value in values) + "</table:table-row>"


def _ehs_fixture() -> bytes:
    sheets: list[str] = []
    owner = (30.0, 40.0)
    social = (10.0, 10.0)
    private = (10.0, 20.0)
    total = (50.0, 70.0)
    for year in range(2008, 2019):
        period = f"{year}-{str(year + 1)[-2:]}"
        rows = [
            _row("title"),
            _row("all households"),
            _row("", "16-24", "25-34", "35-44", "total", "sample size"),
            _row("", "", "", "", "thousands of households"),
            _row("all owner occupiers", 0, owner[0], owner[1], sum(owner)),
            _row("all social renters", 0, social[0], social[1], sum(social)),
            _row("all private renters", 0, private[0], private[1], sum(private)),
            _row("all tenures", 0, total[0], total[1], sum(total)),
            _row("", "", "", "", "percentages within tenure"),
            _row("all owner occupiers", 0, 1, 1, 100),
            _row("all social renters", 0, 1, 1, 100),
            _row("all private renters", 0, 1, 1, 100),
            _row("all tenures", 0, 1, 1, 100),
            _row("", "", "percentages within age group"),
            _row("all owner occupiers", 0, 60, 100 * 40 / 70, 100 * 70 / 120),
            _row("all social renters", 0, 20, 100 * 10 / 70, 100 * 20 / 120),
            _row("all private renters", 0, 20, 100 * 20 / 70, 100 * 30 / 120),
            _row("all tenures", 100, 100, 100, 100),
        ]
        if year != 2013:
            rows.append(_row("sample size", 10, 100, 120, 230))
        sheets.append(f'<table:table table:name="{period}">' + "".join(rows) + "</table:table>")
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        "<office:body><office:spreadsheet>"
        + "".join(sheets)
        + "</office:spreadsheet></office:body></office:document-content>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "mimetype",
            "application/vnd.oasis.opendocument.spreadsheet",
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr("content.xml", content)
    return output.getvalue()


def _single_sheet_ods(sheet: str, rows: list[str]) -> bytes:
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
        'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" '
        'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
        "<office:body><office:spreadsheet>"
        f'<table:table table:name="{sheet}">'
        + "".join(rows)
        + "</table:table></office:spreadsheet></office:body></office:document-content>"
    )
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "mimetype",
            "application/vnd.oasis.opendocument.spreadsheet",
            compress_type=zipfile.ZIP_STORED,
        )
        archive.writestr("content.xml", content)
    return output.getvalue()


def _supply_fixtures(
    *,
    reorder_stock_header: bool = False,
    duplicate_stock_year: bool = False,
    bad_financial_year: bool = False,
) -> tuple[bytes, bytes]:
    stock_header = [
        "Date",
        "Year",
        "Owner occupied",
        "Rented privately or with a job or business",
        "Rented from private registered providers",
        "Rented from local authorities",
        "Other public sector dwellings",
        "All dwellings",
        "Notes",
    ]
    if reorder_stock_header:
        stock_header[6], stock_header[7] = stock_header[7], stock_header[6]
    stock_rows = [_row(*stock_header)]
    for year in range(2008, 2019):
        stock_rows.append(_row("31 March", year, 600, 200, 100, 50, 50, 1000 + year))
    if duplicate_stock_year:
        stock_rows.append(_row("31 March", 2008, 600, 200, 100, 50, 50, 3008))

    periods = [f"{year}-{str(year + 1)[-2:]}" for year in range(2008, 2019)]
    if bad_financial_year:
        periods[0] = "2008 revised"
    supply_rows = [_row("Components of net housing supply", *periods)]
    values = {
        "New build completions": 100,
        "Net conversions": 10,
        "Net change of use": 5,
        "Net other gains": 0,
        "Demolitions": 5,
        "Census adjustments": 0,
        "Total net additional dwellings": 110,
    }
    supply_rows.extend(_row(label, *([value] * 11)) for label, value in values.items())
    return (
        _single_sheet_ods("LT_104", stock_rows),
        _single_sheet_ods("LT120_unrounded", supply_rows),
    )


def test_ehs_extractor_binds_count_section_and_preserves_missing_age_sample() -> None:
    checks = extraction._Checks()
    rows = extraction._extract_ehs(_ehs_fixture(), checks)
    assert len(rows) == 11
    assert rows[0]["owner_share_pct"] == pytest.approx(100 * 70 / 120)
    assert rows[0]["unweighted_sample_size_25_44"] == 220
    assert rows[5]["period"] == "2013-14"
    assert rows[5]["unweighted_sample_size_25_44"] is None
    assert all(check.status == "PASS" for check in checks.items)


def test_payload_set_rehashes_bytes_before_parsing() -> None:
    payload = b"date,value\n2020-01-01,1\n"
    source = SourceSpec(
        source_id="TEST",
        publisher="Test",
        landing_url="https://example.org/landing",
        download_url="https://example.org/test.csv",
        filename="test.csv",
        sha256=hashlib.sha256(payload).hexdigest(),
        allowed_hosts=("example.org",),
        media_kind="csv",
        max_bytes=1024,
        access_tier="open_download",
        licence="test",
    )
    config = GateAConfig(
        schema_version="0.1",
        protocol_version="test",
        seed=20260801,
        core_start_year=2008,
        core_end_year=2019,
        user_agent="test",
        sources=(source,),
        blocked_outputs=MappingProxyType({"blocked": "test"}),
    )
    validate_payload_set(config, {"TEST": payload})
    with pytest.raises(InvariantViolation, match="hash drift"):
        validate_payload_set(config, {"TEST": payload + b"mutation"})
    with pytest.raises(InvariantViolation, match="payload IDs differ"):
        validate_payload_set(config, {})


def test_supply_extractor_binds_stock_schema_dates_and_exact_financial_years() -> None:
    stock, supply = _supply_fixtures()
    checks = extraction._Checks()
    rows = extraction._extract_supply(stock, supply, checks)
    assert len(rows) == 11
    assert rows[0]["financial_year"] == "2008-09"
    assert rows[0]["stock_reference_date"] == "2008-03-31"
    assert rows[0]["published_component_residual"] == 0
    assert all(check.status == "PASS" for check in checks.items)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ({"reorder_stock_header": True}, "exact registered LT104 header"),
        ({"duplicate_stock_year": True}, "duplicate year 2008"),
        ({"bad_financial_year": True}, "exact period '2008-09'"),
    ),
)
def test_supply_schema_mutations_fail_closed(mutation: dict[str, bool], message: str) -> None:
    stock, supply = _supply_fixtures(**mutation)
    with pytest.raises(InvariantViolation, match=message):
        extraction._extract_supply(stock, supply, extraction._Checks())
