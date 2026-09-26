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
    add_language_args,
    add_output_args,
    add_scan_input_args,
    configure_logging,
    filter_dataframe_by_languages,
    load_scan_csv,
    resolve_filters,
    savefig,
    setup_style,
    write_dataframe,
)

log = logging.getLogger(__name__)

PREVALENCE_RATE_TICK_STEP = 2.0


def compute_prevalence_axis_limits(
    found_counts: pd.Series,
    prevalence_pct: pd.Series,
) -> tuple[float, float, float, float]:
    count_max = max(float(found_counts.max() or 0.0), 1.0)
    rate_max = max(float(prevalence_pct.max() or 0.0), 1.0)
    count_magnitude = 10 ** max(0, int(np.floor(np.log10(count_max))))
    count_step = count_magnitude if count_max / count_magnitude <= 8 else count_magnitude * 2
    count_axis_max = float(np.ceil(count_max / count_step) * count_step)
    count_xlim_max = count_axis_max * 1.06
    prevalence_axis_max = float(np.ceil(rate_max / PREVALENCE_RATE_TICK_STEP) * PREVALENCE_RATE_TICK_STEP)
    prevalence_xlim_max = prevalence_axis_max * 1.05
    return count_axis_max, count_xlim_max, prevalence_axis_max, prevalence_xlim_max


def compute_prevalence_rate_ticks(prevalence_axis_max: float) -> np.ndarray:
    return np.arange(0, prevalence_axis_max + PREVALENCE_RATE_TICK_STEP, PREVALENCE_RATE_TICK_STEP)


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

    fig, ax_count = plt.subplots(figsize=(12.0, max(4.0, len(plot_df) * 0.42 + 1.8)))
    ax_rate = ax_count.twiny()

    y_positions = np.arange(len(plot_df)) * 0.72
    bar_height = 0.17
    bar_offset = 0.095
    count_axis_max, count_xlim_max, prevalence_axis_max, prevalence_xlim_max = compute_prevalence_axis_limits(
        plot_df["found_count"],
        plot_df["prevalence_pct"],
    )

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
        "Repos with SKILL.md (count)", fontsize=18, fontweight="bold", labelpad=14
    )
    ax_rate.set_xlabel("Prevalence rate (%)", fontsize=18, fontweight="bold", labelpad=14)
    ax_count.set_xlim(0, count_xlim_max)
    ax_rate.set_xlim(0, prevalence_xlim_max)
    ax_count.set_xticks(np.arange(0, count_axis_max + (count_axis_max / 5), count_axis_max / 5))
    ax_rate.set_xticks(compute_prevalence_rate_ticks(prevalence_axis_max))
    ax_count.tick_params(axis="x", labelsize=16)
    ax_count.tick_params(axis="y", labelsize=16)
    ax_rate.tick_params(axis="x", labelsize=16)
    ax_count.grid(axis="x", color="#d0d0d0", linewidth=0.8, alpha=0.55)
    ax_count.grid(axis="y", visible=False)
    ax_rate.grid(False)

    for bar, row in zip(count_bars, plot_df.itertuples(index=False)):
        y_center = bar.get_y() + bar.get_height() / 2
        label_x = min(float(row.found_count) + max(count_xlim_max * 0.012, 1.0), count_xlim_max - max(count_xlim_max * 0.012, 1.0))
        label_ha = "right" if label_x >= count_xlim_max - max(count_xlim_max * 0.012, 1.0) else "left"
        ax_count.text(
            label_x,
            y_center,
            f"{int(row.found_count):,}",
            va="center",
            ha=label_ha,
            fontsize=15,
            fontweight="bold",
            color="#1f1f1f",
        )

    for bar, row in zip(rate_bars, plot_df.itertuples(index=False)):
        y_center = bar.get_y() + bar.get_height() / 2
        label_x = min(float(row.prevalence_pct) + max(prevalence_xlim_max * 0.015, 0.05), prevalence_xlim_max - 0.06)
        label_ha = "right" if label_x >= prevalence_xlim_max - 0.06 else "left"
        ax_rate.text(
            label_x,
            y_center,
            f"{row.prevalence_pct:.1f}%",
            va="center",
            ha=label_ha,
            fontsize=15,
            fontweight="bold",
            color="#D81B60",
        )

    handles_count, labels_count = ax_count.get_legend_handles_labels()
    handles_rate, labels_rate = ax_rate.get_legend_handles_labels()
    # Move the legend below the figure and stack it vertically (one legend item per row)
    fig.legend(
        handles_count + handles_rate,
        labels_count + labels_rate,
        loc="lower center",
        bbox_to_anchor=(0.89, -0.05),
        ncol=1,  # Set to 1 column for a vertical stack
        frameon=True,
        fontsize=14,
        handleheight=1.0,
        borderaxespad=0.0,
    )

    output_path = Path(out_dir) / f"fig1_prevalence_by_language.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 1 and Table 2 for RQ1")
    add_scan_input_args(parser)
    add_language_args(parser)
     
    add_output_args(parser)
    args = parser.parse_args(argv)

    configure_logging(args.log_level)
    setup_style()
    blacklist, filter_words = resolve_filters(args)
    scan_df = load_scan_csv(args.scan_csv, blacklist=blacklist, filter_words=filter_words)
    scan_df = filter_dataframe_by_languages(scan_df, args.languages)
    generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
