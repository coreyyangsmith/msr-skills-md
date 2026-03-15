from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import (
    add_output_args,
    add_scan_input_args,
    configure_logging,
    load_scan_csv,
    prevalence_by_bucket,
    resolve_filters,
    savefig,
    setup_style,
    write_dataframe,
    write_missing_data_note,
)

log = logging.getLogger(__name__)

LABELS = ["<1 MB", "1-<10 MB", "10-<100 MB", "100+ MB"]


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    if "size" not in scan_df.columns or not scan_df["size"].notna().any():
        write_missing_data_note(
            out_dir,
            "fig13_presence_by_project_size",
            "GitHub repository size is unavailable in the current scan CSV.",
            missing_columns=["size"],
        )
        return None

    size_kb = pd.to_numeric(scan_df["size"], errors="coerce")
    buckets = pd.cut(size_kb, bins=[0, 1024, 10240, 102400, float("inf")], labels=LABELS, right=False, include_lowest=True)
    table = prevalence_by_bucket(scan_df, size_kb, "project_size_tier", LABELS, buckets)
    if table.empty:
        write_missing_data_note(
            out_dir,
            "fig13_presence_by_project_size",
            "Repository size values were present but no rows could be binned for plotting.",
            missing_columns=["size"],
        )
        return None

    write_dataframe(table, str(Path(out_dir) / "table12_project_size_breakdown.csv"))

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = sns.color_palette("Blues", n_colors=len(table))
    bars = ax.bar(table["project_size_tier"], table["prevalence_pct"], color=colors, edgecolor="white")
    for bar, row in zip(bars, table.itertuples()):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2, f"{int(row.found)}/{int(row.total)}", ha="center", va="bottom", fontsize=9)
    ax.set_xlabel("GitHub size tier")
    ax.set_ylabel("Prevalence rate (%)")
    ax.set_title("SKILL.md Presence by Project Size")

    output_path = Path(out_dir) / f"fig13_presence_by_project_size.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 13 and Table 12 for RQ1")
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
