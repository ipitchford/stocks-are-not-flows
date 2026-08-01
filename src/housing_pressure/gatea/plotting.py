"""Descriptive figures for the source-bound public accounting paths."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

import matplotlib

from housing_pressure.ident0.errors import InvariantViolation

from .extract import DerivedTable

matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "housing-gatea-20260801"
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402


_COLORS = {
    "navy": "#17365D",
    "blue": "#2E75B6",
    "orange": "#C55A11",
    "green": "#548235",
    "gray": "#666666",
}


def _table_map(tables: Sequence[DerivedTable]) -> Mapping[str, DerivedTable]:
    result = {table.filename: table for table in tables}
    if len(result) != len(tables):
        raise InvariantViolation("figure input tables have duplicate filenames")
    return result


def _save_figure(figure: plt.Figure, base: Path) -> tuple[Path, Path]:
    base.parent.mkdir(parents=True, exist_ok=True)
    pdf = base.with_suffix(".pdf")
    svg = base.with_suffix(".svg")
    if pdf.exists() or svg.exists():
        raise InvariantViolation(f"refusing to overwrite Gate A figure: {base}")
    figure.savefig(
        pdf,
        bbox_inches="tight",
        metadata={"Creator": "housing-gatea", "CreationDate": None, "ModDate": None},
    )
    figure.savefig(
        svg,
        bbox_inches="tight",
        metadata={"Creator": "housing-gatea", "Date": "2026-08-01"},
    )
    plt.close(figure)
    return pdf, svg


def _style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color="#DDDDDD", linewidth=0.7)
    axis.set_axisbelow(True)


def create_figures(tables: Sequence[DerivedTable], directory: Path) -> tuple[Path, ...]:
    """Create three descriptive figures; no line is interpreted causally."""

    by_name = _table_map(tables)
    outputs: list[Path] = []

    tenure = by_name["ehs_tenure_25_44_england.csv"].rows
    figure, axis = plt.subplots(figsize=(7.2, 4.4), layout="constrained")
    years = [int(row["start_year"]) for row in tenure]
    axis.plot(
        years,
        [row["owner_share_pct"] for row in tenure],
        marker="o",
        label="Owner",
        color=_COLORS["navy"],
    )
    axis.plot(
        years,
        [row["private_renter_share_pct"] for row in tenure],
        marker="o",
        label="Private renter",
        color=_COLORS["orange"],
    )
    axis.plot(
        years,
        [row["social_renter_share_pct"] for row in tenure],
        marker="o",
        label="Social renter",
        color=_COLORS["green"],
    )
    axis.set(
        title="Broad tenure among England households with HRP age 25–44",
        xlabel="EHS financial year starting",
        ylabel="Share (percent)",
    )
    axis.legend(frameon=False, ncol=3)
    axis.set_xticks(years[::2])
    _style_axis(axis)
    outputs.extend(_save_figure(figure, directory / "figure_1_tenure_25_44"))

    ratio = by_name["price_to_stock_rent_2015_2019_england.csv"].rows
    figure, axis = plt.subplots(figsize=(7.2, 4.4), layout="constrained")
    dates = [row["date"] for row in ratio]
    axis.plot(
        dates,
        [100.0 * row["hpi_normalized_jan2015"] for row in ratio],
        label="House-price index",
        color=_COLORS["navy"],
    )
    axis.plot(
        dates,
        [100.0 * row["stock_rent_index_normalized_jan2015"] for row in ratio],
        label="Stock-rent index",
        color=_COLORS["orange"],
    )
    axis.plot(
        dates,
        [100.0 * row["price_to_stock_rent_index"] for row in ratio],
        label="Relative price / stock-rent index",
        color=_COLORS["green"],
    )
    axis.axhline(100.0, color=_COLORS["gray"], linewidth=0.8)
    axis.set(
        title="England price and stock-rent indices, January 2015 = 100",
        xlabel="Month",
        ylabel="Normalized index",
    )
    axis.xaxis.set_major_locator(mdates.YearLocator())
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axis.legend(frameon=False)
    _style_axis(axis)
    outputs.extend(_save_figure(figure, directory / "figure_2_price_stock_rent"))

    supply = by_name["net_additions_2008_2018_england.csv"].rows
    rates = by_name["quoted_mortgage_rates_2008_2019_uk.csv"].rows
    common = [row for row in rates if row["btl_2y_fixed_75ltv_pct"] is not None]
    figure, axes = plt.subplots(2, 1, figsize=(7.2, 7.0), layout="constrained")
    axes[0].bar(
        [int(row["start_year"]) for row in supply],
        [row["net_additions_rate_pct"] for row in supply],
        color=_COLORS["blue"],
    )
    axes[0].set(
        title="England net additional dwellings",
        xlabel="Financial year starting",
        ylabel="Percent of start-year dwelling stock",
    )
    axes[0].set_xticks([int(row["start_year"]) for row in supply][::2])
    _style_axis(axes[0])
    axes[1].plot(
        [row["date"] for row in common],
        [row["owner_2y_fixed_75ltv_pct"] for row in common],
        label="Owner 2-year fixed, 75% LTV",
        color=_COLORS["navy"],
    )
    axes[1].plot(
        [row["date"] for row in common],
        [row["btl_2y_fixed_75ltv_pct"] for row in common],
        label="BTL 2-year fixed, 75% LTV",
        color=_COLORS["orange"],
    )
    axes[1].set(
        title="UK quoted mortgage rates on exact common support",
        xlabel="Month",
        ylabel="Quoted rate (percent)",
    )
    axes[1].xaxis.set_major_locator(mdates.YearLocator(2))
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    axes[1].legend(frameon=False)
    _style_axis(axes[1])
    outputs.extend(_save_figure(figure, directory / "figure_3_supply_and_rates"))
    return tuple(outputs)


__all__ = ["create_figures"]
