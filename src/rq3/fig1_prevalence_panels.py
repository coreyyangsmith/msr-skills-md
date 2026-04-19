#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import pandas as pd

from rq1.common import configure_logging, savefig, setup_style

log = logging.getLogger(__name__)


SDLC_LABEL_ORDER = [
    "Software Testing",
    "Code Generation",
    "DevOps",
    "Documentation",
    "Software Design",
    "Requirements",
]

STRUCTURAL_LABEL_ORDER = [
    "instructive",
    "reference",
    "descriptive",
    "positive-examples",
    "commands",
    "negative-examples",
]

STRUCTURAL_DISPLAY_NAMES = {
    "instructive": "Instructive",
    "reference": "Reference",
    "descriptive": "Descriptive",
    "positive-examples": "Positive-examples",
    "commands": "Commands",
    "negative-examples": "Negative-examples",
}


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def load_python_all_table(path: Path, labels: list[str]) -> pd.DataFrame:
    df = pd.read_csv(path)
    required_columns = {"dataset", "label", "count", "pct_docs", "retained_documents"}
    missing = required_columns - set(df.columns)
    if missing:
        raise SystemExit(f"{path} is missing required columns: {', '.join(sorted(missing))}")

    plot_df = df[df["dataset"] == "Python All"].copy()
    if plot_df.empty:
        raise SystemExit(f"{path} does not contain rows for dataset='Python All'.")

    plot_df["label"] = pd.Categorical(plot_df["label"], categories=labels, ordered=True)
    plot_df = plot_df.sort_values("label").reset_index(drop=True)
    if plot_df["label"].isna().any():
        bad_labels = sorted(set(df[df["dataset"] == "Python All"]["label"]) - set(labels))
        raise SystemExit(f"{path} contains unexpected labels: {', '.join(bad_labels)}")

    return plot_df.sort_values(["pct_docs", "count"], ascending=[False, False]).reset_index(drop=True)


def add_panel(ax: plt.Axes, df: pd.DataFrame, *, title: str, color: str, display_names: dict[str, str] | None = None) -> None:
    labels = [display_names.get(str(label), str(label)) if display_names else str(label) for label in df["label"]]
    bars = ax.barh(labels, df["pct_docs"], color=color, edgecolor="white", linewidth=1.2)
    ax.invert_yaxis()
    ax.set_title(title, loc="left", fontweight="bold", pad=10)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.grid(axis="x", color="#d8d8d8", linewidth=0.8)
    ax.grid(axis="y", visible=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)

    for bar, (_, row) in zip(bars, df.iterrows()):
        width = float(row["pct_docs"])
        y = bar.get_y() + bar.get_height() / 2
        ax.text(
            width + 1.0,
            y,
            f"{width:.1f}% (n={int(row['count'])})",
            va="center",
            ha="left",
            fontsize=9.5,
            color="#333333",
        )


def plot_fig1(sdlc_df: pd.DataFrame, structural_df: pd.DataFrame, output_path: Path, dpi: int) -> None:
    max_pct = max(float(sdlc_df["pct_docs"].max()), float(structural_df["pct_docs"].max()))
    x_max = min(100, max(10, ((int(max_pct) // 10) + 2) * 10))
    retained_counts = set(sdlc_df["retained_documents"].astype(int)) | set(structural_df["retained_documents"].astype(int))
    denominator = retained_counts.pop() if len(retained_counts) == 1 else None

    fig, axes = plt.subplots(1, 2, figsize=(12.8, 5.8), sharex=True, constrained_layout=False)
    fig.subplots_adjust(left=0.10, right=0.98, top=0.88, bottom=0.20, wspace=0.30)
    add_panel(
        axes[0],
        sdlc_df,
        title="Panel A: SDLC label prevalence",
        color="#3F6FA8",
    )
    add_panel(
        axes[1],
        structural_df,
        title="Panel B: Instruction-pattern prevalence",
        color="#D47A2A",
        display_names=STRUCTURAL_DISPLAY_NAMES,
    )

    for ax in axes:
        ax.set_xlim(0, x_max)
        ax.xaxis.set_major_formatter(lambda x, _pos: f"{x:.0f}%")

    note = "Multi-label coding; percentages exceed 100% across categories."
    if denominator is not None:
        note = f"{note} Denominator: {denominator} labeled SKILL.md files."
    fig.supxlabel("Percent of labeled SKILL.md files", y=0.085, fontsize=11)
    fig.text(0.10, 0.035, note, ha="left", va="bottom", fontsize=9.5, color="#555555")
    savefig(fig, str(output_path), dpi=dpi)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate RQ3 fig1 two-panel prevalence chart.")
    parser.add_argument(
        "--sdlc-table",
        default="outputs/rq3/analysis/python_all/table_rq3_python_all_sdlc_tasks.csv",
        help="CSV table with Python All SDLC task prevalence.",
    )
    parser.add_argument(
        "--structural-table",
        default="outputs/rq3/analysis/python_all/table_rq3_python_all_structural_patterns.csv",
        help="CSV table with Python All instruction-pattern prevalence.",
    )
    parser.add_argument(
        "--out",
        default="outputs/rq3/analysis/fig1.png",
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

    sdlc_df = load_python_all_table(resolve_path(args.sdlc_table), SDLC_LABEL_ORDER)
    structural_df = load_python_all_table(resolve_path(args.structural_table), STRUCTURAL_LABEL_ORDER)
    output_path = resolve_path(args.out)

    plot_fig1(sdlc_df, structural_df, output_path, args.dpi)
    log.info("Wrote RQ3 fig1: %s", output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
