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
    configure_logging,
    load_scan_csv,
    resolve_filters,
    savefig,
    setup_style,
    write_dataframe,
)

log = logging.getLogger(__name__)


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    lang_col = "mainLanguage" if "mainLanguage" in scan_df.columns else None
    if lang_col is None:
        log.warning("No mainLanguage column; skipping language analysis.")
        return None

    grouped = (
        scan_df.groupby(lang_col, dropna=False)["found"]
        .agg(total="count", found_count="sum")
        .reset_index()
        .rename(columns={lang_col: "language"})
    )
    grouped["language"] = grouped["language"].fillna("(unknown)")
    grouped["found_count"] = grouped[["found_count", "total"]].min(axis=1)
    grouped["prevalence_pct"] = 100.0 * grouped["found_count"] / grouped["total"]
    table = grouped.sort_values("found_count", ascending=False)
    write_dataframe(table, str(Path(out_dir) / "table2_language_breakdown.csv"))

    plot_df = grouped[grouped["found_count"] >= 1].sort_values("found_count", ascending=True)
    if plot_df.empty:
        log.warning("No languages with found repos; skipping language figure.")
        return None

    fig, ax_count = plt.subplots(figsize=(10.5, max(5.3, len(plot_df) * 0.54 + 1.3)))
    ax_rate = ax_count.twiny()

    y_positions = np.arange(len(plot_df)) * 1.05
    bar_height = 0.34
    bar_offset = 0.19
    count_axis_max = 1500
    count_xlim_max = 1580
    prevalence_axis_max = 5.0
    prevalence_xlim_max = 5.25

    count_bars = ax_count.barh(
        y_positions + bar_offset,
        plot_df["found_count"],
        color=PALETTE_FOUND,
        alpha=0.72,
        edgecolor="white",
        linewidth=0.5,
        height=bar_height,
        label="Repos with SKILL.md",
        zorder=2,
    )
    rate_bars = ax_rate.barh(
        y_positions - bar_offset,
        plot_df["prevalence_pct"],
        color="#D81B60",
        alpha=0.82,
        edgecolor="white",
        linewidth=0.5,
        height=bar_height,
        label="Prevalence rate",
        zorder=3,
    )

    ax_count.set_yticks(list(y_positions))
    ax_count.set_yticklabels(plot_df["language"])
    ax_count.set_xlabel(
        "Repos with SKILL.md (count)", fontsize=14, fontweight="bold", labelpad=12
    )
    ax_rate.set_xlabel("Prevalence rate (%)", fontsize=14, fontweight="bold", labelpad=12)
    ax_count.set_xlim(0, count_xlim_max)
    ax_rate.set_xlim(0, prevalence_xlim_max)
    ax_count.set_xticks(np.arange(0, count_axis_max + 1, 300))
    ax_rate.set_xticks(np.arange(0, prevalence_axis_max + 0.1, 1.0))
    ax_count.tick_params(axis="x", labelsize=12)
    ax_count.tick_params(axis="y", labelsize=12)
    ax_rate.tick_params(axis="x", labelsize=12)
    ax_count.grid(axis="x", color="#d0d0d0", linewidth=0.8, alpha=0.55)
    ax_count.grid(axis="y", visible=False)
    ax_rate.grid(False)

    for bar, row in zip(count_bars, plot_df.itertuples(index=False)):
        y_center = bar.get_y() + bar.get_height() / 2
        label_x = min(float(row.found_count) + 20, count_xlim_max - 20)
        label_ha = "right" if label_x >= count_xlim_max - 20 else "left"
        ax_count.text(
            label_x,
            y_center,
            f"{int(row.found_count):,}",
            va="center",
            ha=label_ha,
            fontsize=11,
            fontweight="bold",
            color="#1f1f1f",
        )

    for bar, row in zip(rate_bars, plot_df.itertuples(index=False)):
        y_center = bar.get_y() + bar.get_height() / 2
        label_x = min(float(row.prevalence_pct) + 0.08, prevalence_xlim_max - 0.06)
        label_ha = "right" if label_x >= prevalence_xlim_max - 0.06 else "left"
        ax_rate.text(
            label_x,
            y_center,
            f"{row.prevalence_pct:.1f}%",
            va="center",
            ha=label_ha,
            fontsize=11,
            fontweight="bold",
            color="#D81B60",
        )

    handles_count, labels_count = ax_count.get_legend_handles_labels()
    handles_rate, labels_rate = ax_rate.get_legend_handles_labels()
    ax_count.legend(
        handles_count + handles_rate,
        labels_count + labels_rate,
        loc="lower right",
        frameon=True,
    )

    output_path = Path(out_dir) / f"fig1_prevalence_by_language.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 1 and Table 2 for RQ1")
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
