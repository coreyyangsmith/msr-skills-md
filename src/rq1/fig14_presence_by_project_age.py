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
    compute_project_age_years,
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

LABELS = ["<1 year", "1-<3 years", "3-<5 years", "5+ years"]


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    if "createdAt" not in scan_df.columns or not scan_df["createdAt"].notna().any():
        write_missing_data_note(
            out_dir,
            "fig14_presence_by_project_age",
            "Repository creation timestamps are unavailable in the current scan CSV.",
            missing_columns=["createdAt"],
        )
        return None

    age_years = compute_project_age_years(scan_df)
    buckets = pd.cut(age_years, bins=[0, 1, 3, 5, float("inf")], labels=LABELS, right=False, include_lowest=True)
    table = prevalence_by_bucket(scan_df, age_years, "project_age_tier", LABELS, buckets)
    if table.empty:
        write_missing_data_note(
            out_dir,
            "fig14_presence_by_project_age",
            "Creation timestamps were present but no project ages could be computed for plotting.",
            missing_columns=["createdAt", "scanned_at_utc"],
        )
        return None

    write_dataframe(table, str(Path(out_dir) / "table13_project_age_breakdown.csv"))

    fig, ax = plt.subplots(figsize=(8, 5))
    colors = sns.color_palette("Blues", n_colors=len(table))
    bars = ax.bar(table["project_age_tier"], table["prevalence_pct"], color=colors, edgecolor="white")
    for bar, row in zip(bars, table.itertuples()):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2, f"{int(row.found)}/{int(row.total)}", ha="center", va="bottom", fontsize=9)
    ax.set_xlabel("Project age tier")
    ax.set_ylabel("Prevalence rate (%)")
    ax.set_title("SKILL.md Presence by Project Age")

    output_path = Path(out_dir) / f"fig14_presence_by_project_age.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 14 and Table 13 for RQ1")
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
