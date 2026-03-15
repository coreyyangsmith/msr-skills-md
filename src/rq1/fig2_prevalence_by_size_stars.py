from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import (
    add_output_args,
    add_scan_input_args,
    configure_logging,
    load_scan_csv,
    resolve_filters,
    safe_stars,
    savefig,
    setup_style,
    write_dataframe,
)

log = logging.getLogger(__name__)


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    stars_col = safe_stars(scan_df)
    code_col = scan_df.get("codeLines", pd.Series(dtype=float))

    if stars_col.isna().all() and code_col.isna().all():
        log.warning("No numeric size/stars columns; skipping size analysis.")
        return None

    work = scan_df[["found"]].copy()
    work["stars"] = stars_col.values

    star_bins = [0, 100, 500, 5000, float("inf")]
    star_labels = ["<100", "100-499", "500-4999", ">=5000"]
    work["star_tier"] = pd.cut(work["stars"], bins=star_bins, labels=star_labels, right=False)

    if "codeLines" in scan_df.columns:
        work["codeLines"] = scan_df["codeLines"].values
        code_bins = [0, 1000, 10000, 100000, float("inf")]
        code_labels = ["Small\n(<1K)", "Medium\n(1K-10K)", "Large\n(10K-100K)", "Very Large\n(>100K)"]
        work["size_tier"] = pd.cut(work["codeLines"], bins=code_bins, labels=code_labels, right=False)
    else:
        code_labels = []
        work["size_tier"] = pd.NA

    star_group = (
        work.groupby("star_tier", observed=True)["found"]
        .agg(total="count", found_count="sum")
        .reset_index()
    )
    star_group["prevalence_pct"] = 100.0 * star_group["found_count"] / star_group["total"].replace(0, np.nan)

    has_size = work["size_tier"].notna().any()
    if has_size:
        pivot = (
            work.groupby(["size_tier", "star_tier"], observed=True)["found"]
            .agg(total="count", found_count="sum")
            .reset_index()
        )
        pivot["prevalence_pct"] = 100.0 * pivot["found_count"] / pivot["total"].replace(0, np.nan)
        heat_data = pivot.pivot_table(index="size_tier", columns="star_tier", values="prevalence_pct", observed=True)
        count_data = pivot.pivot_table(index="size_tier", columns="star_tier", values="total", observed=True, aggfunc="sum")

        fig, axes = plt.subplots(1, 2, figsize=(15, 5))

        ax0 = axes[0]
        colors = sns.color_palette("Blues", n_colors=len(star_group))
        bars = ax0.bar(star_group["star_tier"].astype(str), star_group["prevalence_pct"], color=colors, edgecolor="white")
        for bar, row in zip(bars, star_group.itertuples()):
            ax0.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2, f"{row.found_count}/{row.total}", ha="center", va="bottom", fontsize=9)
        ax0.set_xlabel("Star tier")
        ax0.set_ylabel("Prevalence rate (%)")
        ax0.set_title("SKILL.md Prevalence by Repository Popularity")

        ax1 = axes[1]
        annot = heat_data.round(1).astype(str).where(heat_data.notna(), other="-")
        for row_label in heat_data.index:
            for col_label in heat_data.columns:
                total = count_data.loc[row_label, col_label]
                if not np.isnan(total):
                    annot.loc[row_label, col_label] = f"{heat_data.loc[row_label, col_label]:.1f}%\nn={int(total)}"

        sns.heatmap(
            heat_data,
            annot=annot,
            fmt="",
            cmap="YlOrRd",
            linewidths=0.5,
            ax=ax1,
            cbar_kws={"label": "Prevalence %"},
            annot_kws={"size": 9},
        )
        ax1.set_title("SKILL.md Prevalence (%) by\nProject Size x Popularity")
        ax1.set_xlabel("Star tier")
        ax1.set_ylabel("Code lines tier")
    else:
        fig, ax0 = plt.subplots(figsize=(7, 5))
        colors = sns.color_palette("Blues", n_colors=len(star_group))
        bars = ax0.bar(star_group["star_tier"].astype(str), star_group["prevalence_pct"], color=colors, edgecolor="white")
        for bar, row in zip(bars, star_group.itertuples()):
            ax0.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2, f"{row.found_count}/{row.total}", ha="center", va="bottom", fontsize=9)
        ax0.set_xlabel("Star tier")
        ax0.set_ylabel("Prevalence rate (%)")
        ax0.set_title("SKILL.md Prevalence by Repository Popularity")

    output_path = Path(out_dir) / f"fig2_prevalence_by_size_stars.{fig_format}"
    savefig(fig, str(output_path), dpi)

    rows: list[dict[str, object]] = []
    for tier in star_labels:
        subset = work[work["star_tier"] == tier]["found"]
        total = len(subset)
        found = int(subset.sum())
        prevalence = 100.0 * found / total if total else 0.0
        rows.append({"tier_type": "stars", "tier": tier, "total": total, "found": found, "prevalence_pct": round(prevalence, 2)})

    if has_size:
        for tier in code_labels:
            subset = work[work["size_tier"] == tier]["found"]
            total = len(subset)
            found = int(subset.sum())
            prevalence = 100.0 * found / total if total else 0.0
            rows.append(
                {
                    "tier_type": "code_lines",
                    "tier": tier.replace("\n", " "),
                    "total": total,
                    "found": found,
                    "prevalence_pct": round(prevalence, 2),
                }
            )

    write_dataframe(pd.DataFrame(rows), str(Path(out_dir) / "table3_size_star_breakdown.csv"))
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 2 and Table 3 for RQ1")
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
