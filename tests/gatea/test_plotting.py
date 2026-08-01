from __future__ import annotations

from datetime import date
from pathlib import Path
from types import MappingProxyType

from housing_pressure.gatea.extract import DerivedTable
from housing_pressure.gatea.plotting import create_figures


def _table(filename: str, rows: list[dict[str, object]]) -> DerivedTable:
    return DerivedTable(
        filename=filename,
        fieldnames=tuple(rows[0]),
        rows=tuple(MappingProxyType(row) for row in rows),
        source_ids=("TEST",),
        description="test",
    )


def _tables() -> tuple[DerivedTable, ...]:
    return (
        _table(
            "ehs_tenure_25_44_england.csv",
            [
                {
                    "start_year": 2008,
                    "owner_share_pct": 60.0,
                    "private_renter_share_pct": 22.0,
                    "social_renter_share_pct": 18.0,
                },
                {
                    "start_year": 2009,
                    "owner_share_pct": 59.0,
                    "private_renter_share_pct": 23.0,
                    "social_renter_share_pct": 18.0,
                },
            ],
        ),
        _table(
            "price_to_stock_rent_2015_2019_england.csv",
            [
                {
                    "date": date(2015, 1, 1),
                    "hpi_normalized_jan2015": 1.0,
                    "stock_rent_index_normalized_jan2015": 1.0,
                    "price_to_stock_rent_index": 1.0,
                },
                {
                    "date": date(2016, 1, 1),
                    "hpi_normalized_jan2015": 1.1,
                    "stock_rent_index_normalized_jan2015": 1.05,
                    "price_to_stock_rent_index": 1.1 / 1.05,
                },
            ],
        ),
        _table(
            "net_additions_2008_2018_england.csv",
            [
                {"start_year": 2008, "net_additions_rate_pct": 0.8},
                {"start_year": 2009, "net_additions_rate_pct": 0.7},
            ],
        ),
        _table(
            "quoted_mortgage_rates_2008_2019_uk.csv",
            [
                {
                    "date": date(2012, 1, 1),
                    "owner_2y_fixed_75ltv_pct": 3.0,
                    "btl_2y_fixed_75ltv_pct": 5.0,
                },
                {
                    "date": date(2013, 1, 1),
                    "owner_2y_fixed_75ltv_pct": 2.8,
                    "btl_2y_fixed_75ltv_pct": 4.5,
                },
            ],
        ),
    )


def test_pdf_and_svg_figure_bytes_are_replay_deterministic(tmp_path: Path) -> None:
    first = create_figures(_tables(), tmp_path / "first")
    second = create_figures(_tables(), tmp_path / "second")
    assert [path.name for path in first] == [path.name for path in second]
    assert [path.read_bytes() for path in first] == [path.read_bytes() for path in second]
