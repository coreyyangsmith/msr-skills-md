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

from rq1.common import add_output_args, add_scan_input_args, configure_logging, load_scan_csv, resolve_filters, savefig, setup_style
from rq1.fig3_acf_cooccurrence import ACF_COLUMNS

log = logging.getLogger(__name__)


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    present = [column for column in ACF_COLUMNS if column in scan_df.columns]
    if len(present) < 2:
        log.warning("Fewer than 2 ACF columns present; skipping Fig 4 pairwise heatmap.")
        return None

    found_df = scan_df[scan_df["found"]].copy()
    if found_df.empty:
        log.warning("No found repos; skipping Fig 4 pairwise heatmap.")
        return None

    for column in present:
        found_df[column] = pd.to_numeric(found_df[column], errors="coerce").fillna(0).astype(int)

    labels = [ACF_COLUMNS[column] for column in present]
    matrix = np.zeros((len(present), len(present)), dtype=float)
    for row_index, first in enumerate(present):
        for col_index, second in enumerate(present):
            matrix[row_index, col_index] = int((found_df[first] & found_df[second]).sum())

    fig, ax = plt.subplots(figsize=(6, 5))
    sns.heatmap(
        matrix,
        annot=True,
        fmt=".0f",
        xticklabels=labels,
        yticklabels=labels,
        cmap="YlOrRd",
        ax=ax,
        linewidths=0.5,
        cbar_kws={"label": "Co-occurring repos"},
    )
    ax.set_title("Pairwise ACF Co-occurrence\n(SKILL.md repos only)")

    output_path = Path(out_dir) / f"fig4_acf_pairwise_heatmap.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 4 for RQ1")
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
