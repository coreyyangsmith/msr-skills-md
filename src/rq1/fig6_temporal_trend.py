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

from rq1.common import PALETTE_FOUND, add_output_args, add_scan_input_args, configure_logging, load_scan_csv, resolve_filters, savefig, setup_style, write_dataframe

log = logging.getLogger(__name__)


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    date_col = None
    for candidate in ["pushedAt", "createdAt", "lastCommit"]:
        if candidate in scan_df.columns and scan_df[candidate].notna().any():
            date_col = candidate
            break
    if date_col is None:
        log.warning("No datetime column available; skipping temporal analysis.")
        return None

    found_df = scan_df[scan_df["found"] & scan_df[date_col].notna()].copy()
    all_df = scan_df[scan_df[date_col].notna()].copy()
    if found_df.empty:
        log.warning("No dated found repos; skipping temporal analysis.")
        return None

    found_df["month"] = found_df[date_col].dt.tz_convert(None).dt.to_period("M")
    all_df["month"] = all_df[date_col].dt.tz_convert(None).dt.to_period("M")
    trend = pd.concat(
        [
            found_df.groupby("month").size().rename("found"),
            all_df.groupby("month").size().rename("total"),
        ],
        axis=1,
    ).fillna(0)
    trend["prevalence_pct"] = 100.0 * trend["found"] / trend["total"].replace(0, np.nan)
    trend = trend.sort_index()

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    months = [str(month) for month in trend.index]
    x = np.arange(len(months))

    ax0 = axes[0]
    ax0.bar(x, trend["found"], color=PALETTE_FOUND, alpha=0.85, label="With SKILL.md")
    ax0.set_ylabel("Repositories with SKILL.md")
    ax0.set_title(f"SKILL.md Adoption Over Time (by month, {date_col})")
    ax0.legend()

    ax1 = axes[1]
    ax1.plot(x, trend["total"], color="#9E9E9E", linewidth=1.5, linestyle="--", label="Total repos scanned")
    ax1.set_ylabel("Total repos in cohort")
    ax1.set_xticks(x)
    ax1.set_xticklabels(months, rotation=45, ha="right", fontsize=8)
    ax1.legend()

    output_path = Path(out_dir) / f"fig6_temporal_trend.{fig_format}"
    savefig(fig, str(output_path), dpi)
    write_dataframe(trend.reset_index(), str(Path(out_dir) / "table_temporal_trend.csv"))
    return output_path


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
