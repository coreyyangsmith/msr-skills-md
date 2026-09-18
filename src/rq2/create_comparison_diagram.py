"""Compare two TF-IDF runs (e.g. with-duplicates vs without-duplicates,
or old vs new dataset) side by side as paired horizontal bar charts."""

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


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
):
    left_terms, left_scores = load_top_terms(left_csv, top_k)
    right_terms, right_scores = load_top_terms(right_csv, top_k)

    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(title, fontsize=16, fontweight="bold")

    for ax, terms, scores, label, color in [
        (axes[0], left_terms, left_scores, left_label, left_color),
        (axes[1], right_terms, right_scores, right_label, right_color),
    ]:
        y_pos = range(len(terms))
        ax.barh(y_pos, scores, color=color)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(terms, fontsize=11, fontweight="bold")
        ax.invert_yaxis()
        ax.set_xlabel("TF-IDF score", fontsize=10)
        ax.set_title(label, fontsize=13, fontweight="bold", loc="left")
        for spine in ["top", "right"]:
            ax.spines[spine].set_visible(False)
        ax.grid(axis="x", linestyle="-", alpha=0.3)
        ax.grid(axis="y", visible=False)
        for i, v in enumerate(scores):
            ax.text(v, i, f"  {v:,.0f}", va="center", fontsize=9, fontweight="bold")

    plt.tight_layout(rect=[0, 0, 1, 0.95])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    print(f"Saved: {out_path}")


def parse_args():
    p = argparse.ArgumentParser(description="Compare two TF-IDF term rankings side by side.")
    p.add_argument("--left-csv", required=True, type=Path)
    p.add_argument("--right-csv", required=True, type=Path)
    p.add_argument("--left-label", default="Before")
    p.add_argument("--right-label", default="After")
    p.add_argument("--title", default="TF-IDF Comparison")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--left-color", default="#9CA3AF")
    p.add_argument("--right-color", default="#2E8B57")
    return p.parse_args()


def main():
    args = parse_args()
    plot_pair(
        args.left_csv, args.right_csv,
        args.left_label, args.right_label,
        args.title, args.out, args.top_k,
        args.left_color, args.right_color,
    )


if __name__ == "__main__":
    main()