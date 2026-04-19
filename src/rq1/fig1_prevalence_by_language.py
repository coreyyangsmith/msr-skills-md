from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
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

    fig, axes = plt.subplots(1, 2, figsize=(14, max(5, len(plot_df) * 0.45 + 1.5)))

    ax0 = axes[0]
    bars0 = ax0.barh(
        plot_df["language"],
        plot_df["found_count"],
        color=PALETTE_FOUND,
        edgecolor="white",
        linewidth=0.5,
    )
    ax0.set_xlabel("Repos with SKILL.md (count)")
    ax0.set_title("Repositories with SKILL.md\nby Primary Language")
    for bar, found_count in zip(bars0, plot_df["found_count"]):
        ax0.text(
            bar.get_width() + 0.1,
            bar.get_y() + bar.get_height() / 2,
            f"{int(found_count)}",
            va="center",
            fontsize=8,
        )

    ax1 = axes[1]
    bars1 = ax1.barh(
        plot_df["language"],
        plot_df["prevalence_pct"],
        color=PALETTE_FOUND,
        edgecolor="white",
        linewidth=0.5,
    )
    ax1.set_xlabel("Prevalence rate (%)")
    ax1.set_title("SKILL.md Prevalence Rate\nby Primary Language")
    ax1.set_xlim(left=0)
    for bar, prevalence in zip(bars1, plot_df["prevalence_pct"]):
        ax1.text(
            bar.get_width() + 0.3,
            bar.get_y() + bar.get_height() / 2,
            f"{prevalence:.1f}%",
            va="center",
            fontsize=8,
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
