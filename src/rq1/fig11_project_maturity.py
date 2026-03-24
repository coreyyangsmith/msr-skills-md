from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import (
    PALETTE_FOUND,
    PALETTE_NOT_FOUND,
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
    found_df = scan_df[scan_df["found"]].copy()
    not_found_df = scan_df[~scan_df["found"]].copy()
    maturity_columns = [
        ("commits", "Total Commits"),
        ("contributors", "Contributors"),
        ("forks", "Forks"),
        ("releases", "Releases"),
        ("totalIssues", "Total Issues"),
    ]
    available = [(column, label) for column, label in maturity_columns if column in scan_df.columns and scan_df[column].notna().any()]
    if not available:
        log.warning("No maturity columns available; skipping maturity analysis.")
        return None

    figure, axes = plt.subplots(1, len(available), figsize=(len(available) * 3.2, 5))
    if len(available) == 1:
        axes = [axes]

    rows = []
    for ax, (column, label) in zip(axes, available):
        found_values = pd.to_numeric(found_df[column], errors="coerce").dropna()
        not_found_values = pd.to_numeric(not_found_df[column], errors="coerce").dropna()
        boxplot = ax.boxplot(
            [found_values, not_found_values],
            patch_artist=True,
            medianprops={"color": "black", "linewidth": 1.5},
            showfliers=False,
        )
        for patch, color in zip(boxplot["boxes"], [PALETTE_FOUND, PALETTE_NOT_FOUND]):
            patch.set_facecolor(color)
            patch.set_alpha(0.75)
        ax.set_xticks([1, 2])
        ax.set_xticklabels(
            [f"SKILL.md\n(n={len(found_values):,})", f"No SKILL.md\n(n={len(not_found_values):,})"],
            fontsize=9,
        )
        ax.set_title(label, fontsize=10)
        ax.set_yscale("symlog")

        rows.append(
            {
                "metric": label,
                "found_median": round(found_values.median(), 1) if len(found_values) else np.nan,
                "found_mean": round(found_values.mean(), 1) if len(found_values) else np.nan,
                "not_found_median": round(not_found_values.median(), 1) if len(not_found_values) else np.nan,
                "not_found_mean": round(not_found_values.mean(), 1) if len(not_found_values) else np.nan,
            }
        )

    figure.suptitle("Project Maturity: SKILL.md vs. Non-SKILL.md Repositories\n(outliers hidden for clarity)", y=1.02)
    figure.legend(
        handles=[
            mpatches.Patch(color=PALETTE_FOUND, label="SKILL.md repos"),
            mpatches.Patch(color=PALETTE_NOT_FOUND, label="Non-SKILL.md repos"),
        ],
        loc="lower center",
        ncol=2,
        bbox_to_anchor=(0.5, -0.05),
    )

    output_path = Path(out_dir) / f"fig11_project_maturity.{fig_format}"
    savefig(figure, str(output_path), dpi)
    write_dataframe(pd.DataFrame(rows), str(Path(out_dir) / "table10_project_maturity.csv"))
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 11 and Table 10 for RQ1")
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
