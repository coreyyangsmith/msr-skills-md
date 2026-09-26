"""Compare two TF-IDF runs (e.g. with-duplicates vs without-duplicates,
or old vs new dataset) side by side as paired horizontal bar charts."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[2]
UNIGRAM_COLOR = "#2196F3"
BIGRAM_COLOR = "#D81B60"
DEFAULT_GRID_OUT = REPO_ROOT / "outputs/rq2/top10_unigrams_bigrams_all_vs_dedup.png"
DEFAULT_LEFT_UNIGRAMS = REPO_ROOT / "outputs/rq2/tfidf_sklearn_top_terms_global_unigrams.csv"
DEFAULT_LEFT_BIGRAMS = REPO_ROOT / "outputs/rq2/tfidf_sklearn_top_terms_global_bigrams.csv"
DEFAULT_RIGHT_UNIGRAMS = REPO_ROOT / "outputs/rq2/dedup/tfidf_sklearn_top_terms_global_unigrams.csv"
DEFAULT_RIGHT_BIGRAMS = REPO_ROOT / "outputs/rq2/dedup/tfidf_sklearn_top_terms_global_bigrams.csv"


def load_top_terms(csv_path: Path, top_k: int) -> tuple[list[str], list[float]]:
    terms, scores = [], []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= top_k:
                break
            terms.append(row["term"])
            scores.append(float(row["tfidf_sum"]))
    return terms, scores


def _setup_style() -> None:
    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("seaborn-whitegrid")
    plt.rcParams.update(
        {
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
        }
    )


def _draw_ranked_bars(
    ax,
    terms: list[str],
    scores: list[float],
    color: str,
    title: str,
    show_x_label: bool = True,
    bar_height: float = 0.62,
    bar_step: float = 1.0,
    value_labels: list[str] | None = None,
    x_headroom: float = 1.16,
) -> None:
    if bar_step < bar_height:
        raise ValueError("bar_step must be greater than or equal to bar_height")
    y_pos = [index * bar_step for index in range(len(terms))]
    ax.barh(
        y_pos,
        scores,
        height=bar_height,
        color=color,
        alpha=0.85,
        edgecolor="white",
        linewidth=0.6,
        zorder=2,
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(terms, fontsize=10)
    ax.invert_yaxis()
    score_max = max(scores) if scores else 1
    ax.set_xlim(0, score_max * x_headroom)
    ax.set_xlabel(
        "Summed TF-IDF score" if show_x_label else "",
        fontsize=11,
        fontweight="bold",
        labelpad=7,
    )
    ax.set_title(title, fontsize=12, fontweight="bold", loc="left", pad=8)
    ax.set_axisbelow(True)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["bottom", "left"]:
        ax.spines[spine].set_color("#bdbdbd")
        ax.spines[spine].set_linewidth(0.8)
    ax.tick_params(axis="both", length=0)
    ax.grid(axis="x", color="#d0d0d0", linewidth=0.75, alpha=0.45)
    ax.grid(axis="y", visible=False)
    for i, value in enumerate(scores):
        ax.text(
            value + score_max * 0.012,
            y_pos[i],
            value_labels[i] if value_labels else f"{value:,.0f}",
            va="center",
            ha="left",
            fontsize=9,
            fontweight="bold",
            color="#2b2b2b",
        )


def plot_pair(
    left_csv: Path,
    right_csv: Path,
    left_label: str,
    right_label: str,
    title: str,
    out_path: Path,
    top_k: int = 10,
    left_color: str = "#9CA3AF",
    right_color: str = "#2E8B57",
) -> None:
    _setup_style()
    left_terms, left_scores = load_top_terms(left_csv, top_k)
    right_terms, right_scores = load_top_terms(right_csv, top_k)

    fig, axes = plt.subplots(1, 2, figsize=(20, 6), gridspec_kw={"wspace": 0.7})
    fig.suptitle(title, fontsize=16, fontweight="bold")

    _draw_ranked_bars(axes[0], left_terms, left_scores, left_color, left_label)
    _draw_ranked_bars(axes[1], right_terms, right_scores, right_color, right_label)

    fig.subplots_adjust(top=0.86, wspace=0.85, left=0.18, right=0.98)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_unigram_bigram_grid(
    left_unigrams_csv: Path,
    left_bigrams_csv: Path,
    right_unigrams_csv: Path,
    right_bigrams_csv: Path,
    out_path: Path,
    top_k: int = 10,
    left_label: str = "Full corpus",
    right_label: str = "Deduplicated corpus",
    figsize: tuple[float, float] = (13, 8.5),
    bar_height: float = 0.62,
    bar_step: float = 1.0,
    column_space: float = 0.34,
    row_space: float = 0.32,
    unigram_color: str = UNIGRAM_COLOR,
    bigram_color: str = BIGRAM_COLOR,
    dpi: int = 300,
) -> plt.Figure:
    _setup_style()
    panels = [
        (0, 0, left_unigrams_csv, "Unigrams", unigram_color),
        (0, 1, right_unigrams_csv, "Unigrams", unigram_color),
        (1, 0, left_bigrams_csv, "Bigrams", bigram_color),
        (1, 1, right_bigrams_csv, "Bigrams", bigram_color),
    ]

    fig, axes = plt.subplots(2, 2, figsize=figsize)
    for row, col, csv_path, title, color in panels:
        terms, scores = load_top_terms(csv_path, top_k)
        _draw_ranked_bars(
            axes[row, col],
            terms,
            scores,
            color,
            title,
            show_x_label=row == 1,
            bar_height=bar_height,
            bar_step=bar_step,
        )

    fig.text(0.34, 0.965, f"(a) {left_label}", ha="center", fontsize=14, fontweight="bold")
    fig.text(0.80, 0.965, f"(b) {right_label}", ha="center", fontsize=14, fontweight="bold")
    fig.subplots_adjust(
        top=0.91,
        bottom=0.09,
        left=0.16,
        right=0.98,
        wspace=column_space,
        hspace=row_space,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)
    print(f"Saved: {out_path}")
    return fig


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two TF-IDF term rankings side by side.")
    parser.add_argument(
        "--grid",
        action="store_true",
        help="Write a 2x2 figure: (a) full corpus vs (b) deduplicated, unigrams over bigrams.",
    )
    parser.add_argument("--left-csv", type=Path, help="Left-panel CSV for the 1x2 comparison.")
    parser.add_argument("--right-csv", type=Path, help="Right-panel CSV for the 1x2 comparison.")
    parser.add_argument("--left-unigrams", type=Path, default=DEFAULT_LEFT_UNIGRAMS)
    parser.add_argument("--left-bigrams", type=Path, default=DEFAULT_LEFT_BIGRAMS)
    parser.add_argument("--right-unigrams", type=Path, default=DEFAULT_RIGHT_UNIGRAMS)
    parser.add_argument("--right-bigrams", type=Path, default=DEFAULT_RIGHT_BIGRAMS)
    parser.add_argument("--left-label", default="")
    parser.add_argument("--right-label", default="")
    parser.add_argument("--title", default="TF-IDF Comparison")
    parser.add_argument("--out", type=Path, help="Output image path.")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--left-color", default="#9CA3AF")
    parser.add_argument("--right-color", default="#2E8B57")
    parser.add_argument("--fig-width", type=float, default=13.0)
    parser.add_argument("--fig-height", type=float, default=8.5)
    parser.add_argument("--bar-height", type=float, default=0.62)
    parser.add_argument("--bar-step", type=float, default=1.0)
    parser.add_argument("--column-space", type=float, default=0.34)
    parser.add_argument("--row-space", type=float, default=0.32)
    parser.add_argument("--unigram-color", default=UNIGRAM_COLOR)
    parser.add_argument("--bigram-color", default=BIGRAM_COLOR)
    parser.add_argument("--dpi", type=int, default=300)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.grid:
        plot_unigram_bigram_grid(
            left_unigrams_csv=args.left_unigrams,
            left_bigrams_csv=args.left_bigrams,
            right_unigrams_csv=args.right_unigrams,
            right_bigrams_csv=args.right_bigrams,
            out_path=args.out or DEFAULT_GRID_OUT,
            top_k=args.top_k,
            left_label=args.left_label or "Full corpus",
            right_label=args.right_label or "Deduplicated corpus",
            figsize=(args.fig_width, args.fig_height),
            bar_height=args.bar_height,
            bar_step=args.bar_step,
            column_space=args.column_space,
            row_space=args.row_space,
            unigram_color=args.unigram_color,
            bigram_color=args.bigram_color,
            dpi=args.dpi,
        )
        return

    if args.left_csv is None or args.right_csv is None or args.out is None:
        raise SystemExit("--left-csv, --right-csv, and --out are required unless --grid is set")

    plot_pair(
        args.left_csv,
        args.right_csv,
        args.left_label or "Before",
        args.right_label or "After",
        args.title,
        args.out,
        args.top_k,
        args.left_color,
        args.right_color,
    )


if __name__ == "__main__":
    main()
