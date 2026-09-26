#!/usr/bin/env python3
"""Generate the dedicated Top 10 RQ2 unigram/bigram comparison figure."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq2.create_comparison_diagram import (
    BIGRAM_COLOR,
    DEFAULT_LEFT_BIGRAMS,
    DEFAULT_LEFT_UNIGRAMS,
    DEFAULT_RIGHT_BIGRAMS,
    DEFAULT_RIGHT_UNIGRAMS,
    REPO_ROOT,
    UNIGRAM_COLOR,
    plot_unigram_bigram_grid,
)

DEFAULT_OUT = REPO_ROOT / "outputs/rq2/top10_unigrams_bigrams_all_vs_dedup.png"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the Top 10 RQ2 TF-IDF comparison figure.")
    parser.add_argument("--left-unigrams", type=Path, default=DEFAULT_LEFT_UNIGRAMS)
    parser.add_argument("--left-bigrams", type=Path, default=DEFAULT_LEFT_BIGRAMS)
    parser.add_argument("--right-unigrams", type=Path, default=DEFAULT_RIGHT_UNIGRAMS)
    parser.add_argument("--right-bigrams", type=Path, default=DEFAULT_RIGHT_BIGRAMS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--left-label", default="Full corpus")
    parser.add_argument("--right-label", default="Deduplicated corpus")
    parser.add_argument("--fig-width", type=float, default=13.0)
    parser.add_argument("--fig-height", type=float, default=7.6)
    parser.add_argument("--bar-height", type=float, default=0.50)
    parser.add_argument("--bar-step", type=float, default=0.72)
    parser.add_argument("--column-space", type=float, default=0.34)
    parser.add_argument("--row-space", type=float, default=0.32)
    parser.add_argument("--unigram-color", default=UNIGRAM_COLOR)
    parser.add_argument("--bigram-color", default=BIGRAM_COLOR)
    parser.add_argument("--dpi", type=int, default=300)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plot_unigram_bigram_grid(
        left_unigrams_csv=args.left_unigrams,
        left_bigrams_csv=args.left_bigrams,
        right_unigrams_csv=args.right_unigrams,
        right_bigrams_csv=args.right_bigrams,
        out_path=args.out,
        top_k=10,
        left_label=args.left_label,
        right_label=args.right_label,
        figsize=(args.fig_width, args.fig_height),
        bar_height=args.bar_height,
        bar_step=args.bar_step,
        column_space=args.column_space,
        row_space=args.row_space,
        unigram_color=args.unigram_color,
        bigram_color=args.bigram_color,
        dpi=args.dpi,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
