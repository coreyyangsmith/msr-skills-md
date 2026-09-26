#!/usr/bin/env python3
"""Plot overall, Python, and TypeScript RQ3 prevalence side by side."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from rq1.common import configure_logging, savefig, setup_style, write_dataframe
from rq3.fig1_prevalence_panels import (
    SDLC_DISPLAY_NAMES,
    STRUCTURAL_DISPLAY_NAMES,
    combine_language_tables,
)

log = logging.getLogger(__name__)

DATASET_ORDER = ("Overall", "Python", "TypeScript")
DATASET_COLORS = {
    "Overall": "#6B7280",
    "Python": "#2196F3",
    "TypeScript": "#D81B60",
}
BAR_HEIGHT = 0.14
BAR_OFFSETS = (-0.17, 0.0, 0.17)
GROUP_STEP = 0.72


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def load_language_table(path: Path, dataset_name: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {"dataset", "label", "count", "pct_docs", "retained_documents"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"{path} is missing required columns: {', '.join(sorted(missing))}")
    result = df[df["dataset"] == dataset_name].copy()
    if result.empty:
        raise SystemExit(f"{path} does not contain dataset={dataset_name!r}")
    return result[["label", "count", "pct_docs", "retained_documents"]]


def add_grouped_panel(
    ax: plt.Axes,
    df: pd.DataFrame,
    *,
    title: str,
    display_names: dict[str, str],
) -> None:
    overall = (
        df[df["dataset"] == "Overall"]
        .sort_values(["pct_docs", "count"], ascending=False)
        .reset_index(drop=True)
    )
    labels = overall["label"].tolist()
    y_centers = np.arange(len(labels)) * GROUP_STEP

    for dataset, offset in zip(DATASET_ORDER, BAR_OFFSETS):
        values = (
            df[df["dataset"] == dataset]
            .set_index("label")
            .reindex(labels)
            .reset_index()
        )
        bars = ax.barh(
            y_centers + offset,
            values["pct_docs"],
            height=BAR_HEIGHT,
            color=DATASET_COLORS[dataset],
            alpha=0.86,
            edgecolor="white",
            linewidth=0.5,
            label=dataset,
            zorder=2,
        )
        for bar, row in zip(bars, values.itertuples(index=False)):
            ax.text(
                float(row.pct_docs) + 0.8,
                bar.get_y() + bar.get_height() / 2,
                f"{row.pct_docs:.1f}% (n={int(row.count)})",
                va="center",
                ha="left",
                fontsize=8,
                fontweight="bold",
                color="#2b2b2b",
            )

    ax.set_yticks(y_centers)
    ax.set_yticklabels(
        [display_names.get(str(label), str(label)) for label in labels],
        fontsize=10,
    )
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.set_xticks(np.arange(0, 101, 20))
    ax.xaxis.set_major_formatter(lambda x, _pos: f"{x:.0f}%")
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=9)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#d0d0d0", linewidth=0.75, alpha=0.45)
    ax.grid(axis="y", visible=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color("#bdbdbd")
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(axis="both", length=0, labelsize=10)


def plot_combined(
    sdlc: pd.DataFrame,
    structural: pd.DataFrame,
    output_path: Path,
    dpi: int,
) -> None:
    fig, axes = plt.subplots(
        1,
        2,
        figsize=(15.5, 5.6),
        sharex=True,
        layout="none",
    )
    fig.subplots_adjust(left=0.13, right=0.985, top=0.87, bottom=0.15, wspace=0.40)

    add_grouped_panel(
        axes[0],
        sdlc,
        title="(a) SDLC label prevalence",
        display_names=SDLC_DISPLAY_NAMES,
    )
    add_grouped_panel(
        axes[1],
        structural,
        title="(b) Instruction-pattern prevalence",
        display_names=STRUCTURAL_DISPLAY_NAMES,
    )

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="lower center",
        bbox_to_anchor=(0.5, 0.015),
        ncol=3,
        frameon=False,
        fontsize=11,
    )
    savefig(fig, str(output_path), dpi=dpi)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot overall, Python, and TypeScript RQ3 prevalence."
    )
    parser.add_argument(
        "--python-sdlc",
        default="outputs/rq3/analysis/python_all/table_rq3_python_all_sdlc_tasks.csv",
    )
    parser.add_argument(
        "--python-structural",
        default="outputs/rq3/analysis/python_all/table_rq3_python_all_structural_patterns.csv",
    )
    parser.add_argument(
        "--typescript-sdlc",
        default="outputs/rq3/analysis/typescript_all/table_rq3_typescript_all_sdlc_tasks.csv",
    )
    parser.add_argument(
        "--typescript-structural",
        default="outputs/rq3/analysis/typescript_all/table_rq3_typescript_all_structural_patterns.csv",
    )
    parser.add_argument(
        "--out",
        default="outputs/rq3/analysis/fig1_overall_python_typescript.png",
    )
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    setup_style()

    python_sdlc = load_language_table(resolve_path(args.python_sdlc), "Python All")
    typescript_sdlc = load_language_table(
        resolve_path(args.typescript_sdlc), "TypeScript All"
    )
    python_structural = load_language_table(
        resolve_path(args.python_structural), "Python All"
    )
    typescript_structural = load_language_table(
        resolve_path(args.typescript_structural), "TypeScript All"
    )

    sdlc = combine_language_tables(python_sdlc, typescript_sdlc)
    structural = combine_language_tables(python_structural, typescript_structural)
    output_path = resolve_path(args.out)

    write_dataframe(
        sdlc,
        str(output_path.with_name(f"{output_path.stem}_sdlc.csv")),
    )
    write_dataframe(
        structural,
        str(output_path.with_name(f"{output_path.stem}_structural.csv")),
    )
    plot_combined(sdlc, structural, output_path, args.dpi)
    log.info("Wrote combined RQ3 figure: %s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
