from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, PercentFormatter

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import PALETTE_FOUND, add_output_args, add_scan_input_args, configure_logging, load_scan_csv, resolve_filters, savefig, setup_style, write_dataframe

log = logging.getLogger(__name__)

PALETTE_ALL_REPOS = "#CDD3DB"
PALETTE_ALL_REPOS_LINE = "#8C97A6"
PALETTE_FOUND_DARK = "#1565C0"
ADOPTION_STEM = "fig6a_adoption_over_time"
PREVALENCE_STEM = "fig6b_prevalence_rate_over_time"


def _month_starts(index: pd.Index) -> pd.DatetimeIndex:
    if isinstance(index, pd.PeriodIndex):
        return index.to_timestamp()
    return pd.to_datetime(index)


def _format_count(value: float, _pos: float) -> str:
    return f"{int(round(value)):,}"


def _configure_month_axis(ax: plt.Axes, dates: pd.DatetimeIndex) -> None:
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=(4, 7, 10)))
    ax.set_xlim(dates.min() - pd.DateOffset(months=1), dates.max() + pd.DateOffset(months=1))
    ax.grid(axis="y", alpha=0.28)
    ax.grid(axis="x", which="major", alpha=0.12)
    ax.grid(axis="x", which="minor", alpha=0.05)


def _build_trend_table(scan_df: pd.DataFrame) -> tuple[pd.DataFrame | None, str | None]:
    date_col = None
    for candidate in ["createdAt", "pushedAt", "lastCommit"]:
        if candidate in scan_df.columns and scan_df[candidate].notna().any():
            date_col = candidate
            break
    if date_col is None:
        return None, None

    found_df = scan_df[scan_df["found"] & scan_df[date_col].notna()].copy()
    all_df = scan_df[scan_df[date_col].notna()].copy()
    if found_df.empty:
        return None, date_col

    found_df["month"] = found_df[date_col].dt.tz_convert(None).dt.to_period("M")
    all_df["month"] = all_df[date_col].dt.tz_convert(None).dt.to_period("M")
    trend = pd.concat(
        [
            found_df.groupby("month").size().rename("found"),
            all_df.groupby("month").size().rename("total"),
        ],
        axis=1,
    ).fillna(0)
    trend["prevalence_pct"] = 100.0 * trend["found"] / trend["total"].replace(0, float("nan"))
    trend = trend.sort_index()
    return trend, date_col


def _plot_adoption_over_time(trend: pd.DataFrame, date_col: str, output_path: Path, dpi: int) -> None:
    dates = _month_starts(trend.index)
    fig, ax_total = plt.subplots(figsize=(13.5, 6.2))
    ax_found = ax_total.twinx()

    ax_total.bar(
        dates,
        trend["total"],
        width=24,
        color=PALETTE_ALL_REPOS,
        edgecolor="white",
        linewidth=0.25,
        alpha=0.95,
        zorder=1,
    )
    ax_total.plot(
        dates,
        trend["total"],
        color=PALETTE_ALL_REPOS_LINE,
        linewidth=1.6,
        alpha=0.95,
        zorder=2,
    )

    ax_found.fill_between(dates, 0, trend["found"], color=PALETTE_FOUND, alpha=0.12, zorder=3)
    ax_found.plot(
        dates,
        trend["found"],
        color=PALETTE_FOUND_DARK,
        linewidth=2.4,
        marker="o",
        markersize=3,
        markerfacecolor="white",
        markeredgecolor=PALETTE_FOUND_DARK,
        markeredgewidth=0.8,
        zorder=4,
    )

    ax_total.set_title(
        f"SKILL.md Adoption Over Time (monthly, by {date_col})",
        loc="left",
        fontweight="bold",
        pad=12,
    )

    ax_total.set_ylabel("All repos in cohort", color=PALETTE_ALL_REPOS_LINE)
    ax_total.yaxis.label.set_fontsize(13)
    ax_total.yaxis.label.set_fontweight("bold")
    ax_found.set_ylabel("Repos with SKILL.md", color=PALETTE_FOUND_DARK)
    ax_found.yaxis.label.set_fontsize(13)
    ax_found.yaxis.label.set_fontweight("bold")
    ax_total.yaxis.set_major_formatter(FuncFormatter(_format_count))
    ax_found.yaxis.set_major_formatter(FuncFormatter(_format_count))
    ax_total.tick_params(axis="y", colors=PALETTE_ALL_REPOS_LINE)
    ax_found.tick_params(axis="y", colors=PALETTE_FOUND_DARK)
    ax_total.set_xlabel("Repository month", fontsize=13)
    ax_total.set_ylim(0, float(trend["total"].max()) * 1.08)
    ax_found.set_ylim(0, float(trend["found"].max()) * 1.12)
    _configure_month_axis(ax_total, dates)

    handles = [
        Patch(facecolor=PALETTE_ALL_REPOS, edgecolor="white", label="All repos (left axis)"),
        Line2D(
            [0],
            [0],
            color=PALETTE_FOUND_DARK,
            linewidth=2.4,
            marker="o",
            markersize=4,
            markerfacecolor="white",
            markeredgecolor=PALETTE_FOUND_DARK,
            label="With SKILL.md (right axis)",
        ),
    ]
    ax_total.legend(handles=handles, loc="upper left", frameon=True)

    savefig(fig, str(output_path), dpi)


def _plot_prevalence_rate(trend: pd.DataFrame, date_col: str, output_path: Path, dpi: int) -> None:
    dates = _month_starts(trend.index)
    overall_prevalence = 100.0 * trend["found"].sum() / trend["total"].sum()

    fig, ax = plt.subplots(figsize=(13.5, 5.4))
    ax.fill_between(dates, 0, trend["prevalence_pct"], color=PALETTE_FOUND, alpha=0.14, zorder=1)
    ax.plot(
        dates,
        trend["prevalence_pct"],
        color=PALETTE_FOUND,
        linewidth=1.5,
        marker="o",
        markersize=2.8,
        alpha=0.7,
        label="Monthly prevalence",
        zorder=2,
    )
    ax.axhline(
        overall_prevalence,
        color="#6D7E8C",
        linestyle="--",
        linewidth=1.3,
        label=f"Overall average ({overall_prevalence:.1f}%)",
        zorder=0,
    )

    ax.set_title(
        f"SKILL.md Prevalence Rate Over Time (monthly, by {date_col})",
        loc="left",
        fontweight="bold",
        pad=12,
    )

    ax.set_ylabel("Prevalence rate")
    ax.set_xlabel("Repository month")
    ax.yaxis.set_major_formatter(PercentFormatter(xmax=100))
    ax.set_ylim(0, float(trend["prevalence_pct"].max()) * 1.12)
    _configure_month_axis(ax, dates)
    ax.legend(loc="upper left", ncol=2, frameon=True)

    savefig(fig, str(output_path), dpi)


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> tuple[Path, Path] | None:
    trend, date_col = _build_trend_table(scan_df)
    if date_col is None:
        log.warning("No datetime column available; skipping temporal analysis.")
        return None

    if trend is None or trend.empty:
        log.warning("No dated found repos; skipping temporal analysis.")
        return None

    adoption_path = Path(out_dir) / f"{ADOPTION_STEM}.{fig_format}"
    prevalence_path = Path(out_dir) / f"{PREVALENCE_STEM}.{fig_format}"
    _plot_adoption_over_time(trend, date_col, adoption_path, dpi)
    _plot_prevalence_rate(trend, date_col, prevalence_path, dpi)
    write_dataframe(trend.reset_index(), str(Path(out_dir) / "table_temporal_trend.csv"))
    return adoption_path, prevalence_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 6 and temporal trend table for RQ1")
    add_scan_input_args(parser)
    add_output_args(parser)
    args = parser.parse_args(argv)

    configure_logging(args.log_level)
    setup_style()
    blacklist, filter_words = resolve_filters(args)
    scan_df = load_scan_csv(args.scan_csv, blacklist=blacklist, filter_words=filter_words)
    generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
