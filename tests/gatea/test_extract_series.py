from __future__ import annotations

import calendar
import csv
from datetime import date, datetime
import io

import openpyxl
import pytest

from housing_pressure.gatea import extract as extraction
from housing_pressure.ident0.errors import InvariantViolation


def _months(start: date, count: int) -> list[date]:
    year, month = start.year, start.month
    output: list[date] = []
    for _ in range(count):
        output.append(date(year, month, 1))
        month += 1
        if month == 13:
            year += 1
            month = 1
    return output


def _hpi(*, drop_index: int | None = None, negative_index: int | None = None) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=["Date", "Region_Name", "Area_Code", "Index"],
        lineterminator="\n",
    )
    writer.writeheader()
    for index, observed_date in enumerate(_months(date(2008, 1, 1), 144)):
        if index == drop_index:
            continue
        writer.writerow(
            {
                "Date": observed_date.isoformat(),
                "Region_Name": "England",
                "Area_Code": "E92000001",
                "Index": -1 if index == negative_index else 60 + index / 10,
            }
        )
    return stream.getvalue().encode()


def _iphrp(
    *, wrong_geography_index: int | None = None, wrong_name_index: int | None = None
) -> bytes:
    fields = [
        "v4_1",
        "Data Marking",
        "mmm-yy",
        "Time",
        "administrative-geography",
        "Geography",
        "index-and-year-change",
        "IndexAndYearChange",
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for index, observed_date in enumerate(_months(date(2008, 1, 1), 84)):
        writer.writerow(
            {
                "v4_1": 90 + index / 10,
                "Data Marking": "",
                "mmm-yy": observed_date.strftime("%b-%y"),
                "Time": observed_date.isoformat(),
                "administrative-geography": (
                    "X00000000" if index == wrong_geography_index else "E92000001"
                ),
                "Geography": "Not England" if index == wrong_name_index else "England",
                "index-and-year-change": "index",
                "IndexAndYearChange": "Index",
            }
        )
    return stream.getvalue().encode()


def _pipr(*, wrong_geography_index: int | None = None, negative_index: int | None = None) -> bytes:
    workbook = openpyxl.Workbook()
    worksheet = workbook.active
    worksheet.title = "Table 1"
    headers = ["Time period", "Area code", "Area name", "Index", "Rental price"] + [
        f"unused_{index}" for index in range(35)
    ]
    worksheet.append([])
    worksheet.append([])
    worksheet.append(headers)
    for index, observed_date in enumerate(_months(date(2015, 1, 1), 60)):
        worksheet.append(
            [
                datetime(observed_date.year, observed_date.month, 1),
                "X00000000" if index == wrong_geography_index else "E92000001",
                "England",
                -1 if index == negative_index else 100 + index / 10,
                800 + index,
                *([None] * 35),
            ]
        )
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def _boe(
    *, missing_common_index: int | None = None, negative_owner_index: int | None = None
) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=["DATE", "IUMBV34", "IUMZID4"],
        lineterminator="\n",
    )
    writer.writeheader()
    for index, observed_date in enumerate(_months(date(2008, 1, 1), 144)):
        last_day = calendar.monthrange(observed_date.year, observed_date.month)[1]
        btl = "" if index < 48 or index == missing_common_index else 4.5
        writer.writerow(
            {
                "DATE": date(observed_date.year, observed_date.month, last_day).strftime(
                    "%d %b %Y"
                ),
                "IUMBV34": -1 if index == negative_owner_index else 3.0,
                "IUMZID4": btl,
            }
        )
    return stream.getvalue().encode()


def test_monthly_extractors_accept_only_complete_registered_support() -> None:
    hpi_checks = extraction._Checks()
    hpi = extraction._extract_hpi(_hpi(), hpi_checks)
    assert len(hpi) == 144
    annual_hpi = extraction._annual_hpi(hpi, hpi_checks)
    assert len(annual_hpi) == 12
    assert annual_hpi[0]["december_to_december_100_log_change"] is None
    assert annual_hpi[1]["december_to_december_100_log_change"] is not None
    assert len(extraction._extract_iphrp(_iphrp(), extraction._Checks())) == 84
    assert len(extraction._extract_pipr(_pipr(), extraction._Checks())) == 60
    boe_checks = extraction._Checks()
    rates = extraction._extract_boe(_boe(), boe_checks)
    assert len(rates) == 144
    annual_rates = extraction._annual_boe(rates, boe_checks)
    assert len(annual_rates) == 12
    assert annual_rates[0]["btl_2y_fixed_75ltv_annual_mean_pct"] is None
    assert annual_rates[4]["btl_common_support_months"] == 12


@pytest.mark.parametrize(
    ("call", "message"),
    (
        (lambda: extraction._extract_hpi(_hpi(drop_index=10), extraction._Checks()), "months"),
        (
            lambda: extraction._extract_hpi(_hpi(negative_index=10), extraction._Checks()),
            "domain",
        ),
        (
            lambda: extraction._extract_iphrp(
                _iphrp(wrong_geography_index=10), extraction._Checks()
            ),
            "months",
        ),
        (
            lambda: extraction._extract_iphrp(_iphrp(wrong_name_index=10), extraction._Checks()),
            "domain",
        ),
        (
            lambda: extraction._extract_pipr(_pipr(wrong_geography_index=10), extraction._Checks()),
            "months",
        ),
        (
            lambda: extraction._extract_pipr(_pipr(negative_index=10), extraction._Checks()),
            "domain",
        ),
        (
            lambda: extraction._extract_boe(_boe(missing_common_index=60), extraction._Checks()),
            "common_support",
        ),
        (
            lambda: extraction._extract_boe(_boe(negative_owner_index=10), extraction._Checks()),
            "positive_rate_domain",
        ),
    ),
)
def test_month_gap_geography_and_domain_mutations_fail_closed(call: object, message: str) -> None:
    with pytest.raises(InvariantViolation, match=message):
        call()
