#!/usr/bin/env python3
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

from rq1.common import configure_logging, savefig, setup_style
from rq3.label_processing import INSTRUCTION_TYPE_LABELS, SDLC_STAGE_LABELS

log = logging.getLogger(__name__)

SDLC_COLOR = "#2196F3"
INSTRUCTION_COLOR = SDLC_COLOR
BAR_HEIGHT = 0.20
BAR_STEP = 0.22


SDLC_LABEL_ORDER = list(SDLC_STAGE_LABELS)

SDLC_DISPLAY_NAMES = {
    "Requirements": "Requirements",
    "Software Design": "Design",
    "Code Implementation": "Implementation",
    "Program Analysis": "Program Analysis",
    "Testing": "Testing",
    "Debugging": "Debugging",
    "Maintenance": "Maintenance",
    "DevOps": "DevOps",
    "Documentation": "Documentation",
}

STRUCTURAL_LABEL_ORDER = list(INSTRUCTION_TYPE_LABELS)

STRUCTURAL_DISPLAY_NAMES = {
    label: label.replace("-", " ").title() for label in INSTRUCTION_TYPE_LABELS
}


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def load_language_all_table(path: Path, labels: list[str], dataset_name: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    required_columns = {"dataset", "label", "count", "pct_docs", "retained_documents"}
    missing = required_columns - set(df.columns)
    if missing:
        raise SystemExit(f"{path} is missing required columns: {', '.join(sorted(missing))}")

    plot_df = df[df["dataset"] == dataset_name].copy()
    if plot_df.empty:
        raise SystemExit(f"{path} does not contain rows for dataset={dataset_name!r}.")

    plot_df["label"] = pd.Categorical(plot_df["label"], categories=labels, ordered=True)
    plot_df = plot_df.sort_values("label").reset_index(drop=True)
    if plot_df["label"].isna().any():
        bad_labels = sorted(set(df[df["dataset"] == dataset_name]["label"]) - set(labels))
        raise SystemExit(f"{path} contains unexpected labels: {', '.join(bad_labels)}")

    return plot_df.sort_values(["pct_docs", "count"], ascending=[False, False]).reset_index(drop=True)


def combine_language_tables(python: pd.DataFrame, typescript: pd.DataFrame) -> pd.DataFrame:
    """Return long-form Overall/Python/TypeScript prevalence rows."""
    labels_python = set(python["label"])
    labels_typescript = set(typescript["label"])
    if labels_python != labels_typescript:
        raise ValueError("Python and TypeScript tables must contain the same labels")

    python_docs = set(python["retained_documents"].astype(int))
    typescript_docs = set(typescript["retained_documents"].astype(int))
    if len(python_docs) != 1 or len(typescript_docs) != 1:
        raise ValueError("Each language table must use one retained-document denominator")

    python_rows = python.copy()
    python_rows["dataset"] = "Python"
    typescript_rows = typescript.copy()
    typescript_rows["dataset"] = "TypeScript"

    counts = (
        pd.concat([python, typescript], ignore_index=True)
        .groupby("label", as_index=False)["count"]
        .sum()
    )
    overall_docs = python_docs.pop() + typescript_docs.pop()
    counts["retained_documents"] = overall_docs
    counts["pct_docs"] = 100.0 * counts["count"] / overall_docs
    counts["dataset"] = "Overall"

    return pd.concat([counts, python_rows, typescript_rows], ignore_index=True)


def overall_prevalence_table(python: pd.DataFrame, typescript: pd.DataFrame) -> pd.DataFrame:
    combined = combine_language_tables(python, typescript)
    overall = combined[combined["dataset"] == "Overall"].copy()
    return overall.sort_values(["pct_docs", "count"], ascending=[False, False]).reset_index(drop=True)


def add_panel(
    ax: plt.Axes,
    df: pd.DataFrame,
    *,
    title: str,
    color: str,
    display_names: dict[str, str] | None = None,
) -> None:
    labels = [display_names.get(str(label), str(label)) if display_names else str(label) for label in df["label"]]
    y_positions = np.arange(len(labels)) * BAR_STEP
    bars = ax.barh(
        y_positions,
        df["pct_docs"],
        height=BAR_HEIGHT,
        color=color,
        alpha=0.85,
        edgecolor="white",
        linewidth=0.6,
        zorder=2,
    )
    ax.set_yticks(y_positions)
    ax.set_yticklabels(labels, fontsize=11)
    ax.invert_yaxis()
    ax.set_title(title, loc="left", fontsize=13, fontweight="bold", pad=9)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#d0d0d0", linewidth=0.75, alpha=0.45)
    ax.grid(axis="y", visible=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for spine in ("bottom", "left"):
        ax.spines[spine].set_color("#bdbdbd")
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(axis="both", length=0, labelsize=10)

    for bar, (_, row) in zip(bars, df.iterrows()):
        width = float(row["pct_docs"])
        y = bar.get_y() + bar.get_height() / 2
        ax.text(
            width + 1.0,
            y,
            f"{width:.1f}% (n={int(row['count'])})",
            va="center",
            ha="left",
            fontsize=10,
            fontweight="bold",
            color="#2b2b2b",
        )


def plot_fig1(sdlc_df: pd.DataFrame, structural_df: pd.DataFrame, output_path: Path, dpi: int) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(13.0, 4.25), sharex=True, constrained_layout=False)
    fig.subplots_adjust(left=0.15, right=0.985, top=0.90, bottom=0.12, wspace=0.42)
    add_panel(
        axes[0],
        sdlc_df,
        title="(a) SDLC label prevalence",
        color=SDLC_COLOR,
        display_names=SDLC_DISPLAY_NAMES,
    )
    add_panel(
        axes[1],
        structural_df,
        title="(b) Instruction-pattern prevalence",
        color=INSTRUCTION_COLOR,
        display_names=STRUCTURAL_DISPLAY_NAMES,
    )

    for ax in axes:
        ax.set_xlim(0, 110)
        ax.set_xticks(np.arange(0, 101, 20))
        ax.xaxis.set_major_formatter(lambda x, _pos: f"{x:.0f}%")

    savefig(fig, str(output_path), dpi=dpi)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RQ3 fig1 two-panel prevalence chart.")
    parser.add_argument(
        "--sdlc-table",
        default="outputs/v1_2026-04-19/rq3/analysis/python_all/table_rq3_python_all_sdlc_tasks.csv",
        help="CSV table with language-all SDLC task prevalence.",
    )
    parser.add_argument(
        "--structural-table",
        default="outputs/v1_2026-04-19/rq3/analysis/python_all/table_rq3_python_all_structural_patterns.csv",
        help="CSV table with language-all instruction-pattern prevalence.",
    )
    parser.add_argument(
        "--dataset-name",
        default="Python All",
        help="Dataset label to select from the input tables, e.g. 'Python All' or 'TypeScript All'.",
    )
    parser.add_argument(
        "--blend-sdlc-table",
        default=None,
        help="Optional second SDLC table to pool with --sdlc-table (document-weighted overall).",
    )
    parser.add_argument(
        "--blend-structural-table",
        default=None,
        help="Optional second structural table to pool with --structural-table.",
    )
    parser.add_argument(
        "--blend-dataset-name",
        default="TypeScript All",
        help="Dataset label to select from the blend tables.",
    )
    parser.add_argument(
        "--out",
        default="outputs/v1_2026-04-19/rq3/analysis/fig1.png",
        help="Output figure path.",
    )
    parser.add_argument("--dpi", type=int, default=300, help="Figure DPI.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    setup_style()

    sdlc_df = load_language_all_table(resolve_path(args.sdlc_table), SDLC_LABEL_ORDER, args.dataset_name)
    structural_df = load_language_all_table(resolve_path(args.structural_table), STRUCTURAL_LABEL_ORDER, args.dataset_name)
    if args.blend_sdlc_table or args.blend_structural_table:
        if not args.blend_sdlc_table or not args.blend_structural_table:
            raise SystemExit("Pass both --blend-sdlc-table and --blend-structural-table.")
        blend_sdlc = load_language_all_table(
            resolve_path(args.blend_sdlc_table),
            SDLC_LABEL_ORDER,
            args.blend_dataset_name,
        )
        blend_structural = load_language_all_table(
            resolve_path(args.blend_structural_table),
            STRUCTURAL_LABEL_ORDER,
            args.blend_dataset_name,
        )
        sdlc_df = overall_prevalence_table(sdlc_df, blend_sdlc)
        structural_df = overall_prevalence_table(structural_df, blend_structural)
    output_path = resolve_path(args.out)

    plot_fig1(sdlc_df, structural_df, output_path, args.dpi)
    log.info("Wrote RQ3 fig1: %s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
