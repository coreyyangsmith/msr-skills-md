from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import (
    PALETTE_FOUND,
    add_output_args,
    add_scan_input_args,
    compute_project_age_years,
    configure_logging,
    load_scan_csv,
    prevalence_by_bucket,
    resolve_filters,
    safe_stars,
    savefig,
    setup_style,
    write_dataframe,
    write_missing_data_note,
)

log = logging.getLogger(__name__)

STAR_LABELS = ["<100", "100-499", "500-4999", ">=5000"]
CONTRIBUTOR_LABELS = ["0-1", "2-5", "6-20", "21-100", "101+"]
SIZE_LABELS = ["<1 MB", "1-<10 MB", "10-<100 MB", "100+ MB"]
AGE_LABELS = ["<1 year", "1-<3 years", "3-<5 years", "5+ years"]


def _build_panel_tables(scan_df: pd.DataFrame) -> list[tuple[str, str, pd.DataFrame]]:
    panels: list[tuple[str, str, pd.DataFrame]] = []

    stars = safe_stars(scan_df)
    star_buckets = pd.cut(
        stars,
        bins=[0, 100, 500, 5000, float("inf")],
        labels=STAR_LABELS,
        right=False,
        include_lowest=True,
    )
    star_table = prevalence_by_bucket(scan_df, stars, "bucket", STAR_LABELS, star_buckets)
    if not star_table.empty:
        panels.append(("(a) Stars", "Stars", star_table))

    if "contributors" in scan_df.columns and scan_df["contributors"].notna().any():
        contributors = pd.to_numeric(scan_df["contributors"], errors="coerce")
        contributor_buckets = pd.cut(
            contributors,
            bins=[0, 2, 6, 21, 101, float("inf")],
            labels=CONTRIBUTOR_LABELS,
            right=False,
            include_lowest=True,
        )
        contributor_table = prevalence_by_bucket(
            scan_df,
            contributors,
            "bucket",
            CONTRIBUTOR_LABELS,
            contributor_buckets,
        )
        if not contributor_table.empty:
            panels.append(("(b) Contributors", "Contributors", contributor_table))

    if "size" in scan_df.columns and scan_df["size"].notna().any():
        size_kb = pd.to_numeric(scan_df["size"], errors="coerce")
        size_buckets = pd.cut(
            size_kb,
            bins=[0, 1024, 10240, 102400, float("inf")],
            labels=SIZE_LABELS,
            right=False,
            include_lowest=True,
        )
        size_table = prevalence_by_bucket(scan_df, size_kb, "bucket", SIZE_LABELS, size_buckets)
        if not size_table.empty:
            panels.append(("(c) Repository Size", "Repository size", size_table))

    if "createdAt" in scan_df.columns and scan_df["createdAt"].notna().any():
        age_years = compute_project_age_years(scan_df)
        age_buckets = pd.cut(
            age_years,
            bins=[0, 1, 3, 5, float("inf")],
            labels=AGE_LABELS,
            right=False,
            include_lowest=True,
        )
        age_table = prevalence_by_bucket(scan_df, age_years, "bucket", AGE_LABELS, age_buckets)
        if not age_table.empty:
            panels.append(("(d) Project Age", "Project age", age_table))

    return panels


def _plot_bar_panel(ax: plt.Axes, table: pd.DataFrame, title: str, xlabel: str, y_max: float) -> None:
    x_positions = np.arange(len(table))
    values = table["prevalence_pct"].astype(float).to_numpy()

    bars = ax.bar(
        x_positions,
        values,
        width=0.62,
        color=PALETTE_FOUND,
        edgecolor="white",
        linewidth=1.0,
        alpha=0.9,
        zorder=2,
    )

    for bar, row in zip(bars, table.itertuples(index=False)):
        value = float(row.prevalence_pct)
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            value + y_max * 0.035,
            f"{value:.1f}%\nn={int(row.total):,}",
            ha="center",
            va="bottom",
            fontsize=12,  # Increased from 9 to 12 for larger label callout text
            fontweight="bold",
            color="#1f1f1f",
            linespacing=1.45,
        )

    ax.set_title(title, fontsize=16, fontweight="bold", pad=10)
    ax.set_xlabel(xlabel, fontsize=16, fontweight="bold", labelpad=12)
    ax.set_xticks(x_positions)
    # --------- Changed fontsize from 10 to 14 for larger x-axis labels
    ax.set_xticklabels(table["bucket"].astype(str), rotation=0, ha="center", fontsize=12)
    ax.set_ylim(0, y_max)
    ax.grid(axis="y", color="#d0d0d0", linewidth=0.8, alpha=0.55)
    ax.grid(axis="x", visible=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    panels = _build_panel_tables(scan_df)
    if len(panels) != 4:
        missing = 4 - len(panels)
        write_missing_data_note(
            out_dir,
            "fig21_scale_visibility_collaboration_age",
            f"Could not build all four panels; {missing} required panel(s) had no usable data.",
            missing_columns=["stars/stargazers", "contributors", "size", "createdAt"],
        )
        return None

    table_rows: list[pd.DataFrame] = []
    for panel_title, panel_label, table in panels:
        panel_table = table.copy()
        panel_table.insert(0, "panel", panel_label)
        panel_table.insert(0, "panel_id", panel_title[:3])
        table_rows.append(panel_table)
    write_dataframe(pd.concat(table_rows, ignore_index=True), str(Path(out_dir) / "table21_scale_visibility_collaboration_age.csv"))

    y_max = max(float(table["prevalence_pct"].max()) for _, _, table in panels)
    y_max = max(1.0, np.ceil((y_max + 0.4) * 2) / 2)

    fig, axes = plt.subplots(1, 4, figsize=(16.5, 4.5), sharey=True)
    for ax, (title, xlabel, table) in zip(axes, panels):
        _plot_bar_panel(ax, table, title, xlabel, y_max)

    axes[0].set_ylabel("Prevalence (%)", fontsize=14, fontweight="bold")
    axes[0].tick_params(axis="y", labelsize=12)
    for ax in axes[1:]:
        ax.tick_params(axis="y", labelleft=False)

    output_path = Path(out_dir) / f"fig21_scale_visibility_collaboration_age.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 21 for RQ1")
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
