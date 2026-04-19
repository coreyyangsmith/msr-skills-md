#!/usr/bin/env python3
"""Create RQ2 TF-IDF top-term bar charts for unigrams and bigrams."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

REPO_ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(
		description="Create horizontal bar charts for top TF-IDF unigrams and bigrams."
	)
	parser.add_argument(
		"--unigrams-csv",
		default=str(REPO_ROOT / "outputs/rq2/tfidf_sklearn_top_terms_global_unigrams.csv"),
		help="CSV with unigram TF-IDF terms (columns: term, tfidf_sum)",
	)
	parser.add_argument(
		"--bigrams-csv",
		default=str(REPO_ROOT / "outputs/rq2/tfidf_sklearn_top_terms_global_bigrams.csv"),
		help="CSV with bigram TF-IDF terms (columns: term, tfidf_sum)",
	)
	parser.add_argument(
		"--out-unigrams-image",
		default=str(REPO_ROOT / "outputs/rq2/top10_unigrams_tfidf_barh.png"),
		help="Output image path for unigram chart",
	)
	parser.add_argument(
		"--out-bigrams-image",
		default=str(REPO_ROOT / "outputs/rq2/top10_bigrams_tfidf_barh.png"),
		help="Output image path for bigram chart",
	)
	parser.add_argument(
		"--out-combined-image",
		default=str(REPO_ROOT / "outputs/rq2/top10_tfidf_unigrams_bigrams_combined.png"),
		help="Output image path for combined unigram+bigram chart",
	)
	parser.add_argument(
		"--skip-separate",
		action="store_true",
		help="Only generate the combined figure and skip separate unigram/bigram images.",
	)
	parser.add_argument(
		"--top-k",
		type=int,
		default=10,
		help="Number of top terms to plot (default: 10)",
	)
	return parser.parse_args()


def load_top_terms(csv_path: Path, top_k: int) -> pd.DataFrame:
	if not csv_path.exists() or not csv_path.is_file():
		raise FileNotFoundError(f"CSV file not found: {csv_path}")

	df = pd.read_csv(csv_path)
	required = {"term", "tfidf_sum"}
	if not required.issubset(df.columns):
		raise ValueError(
			f"CSV {csv_path} must contain columns {sorted(required)}; found {list(df.columns)}"
		)

	top = (
		df[["term", "tfidf_sum"]]
		.dropna(subset=["term", "tfidf_sum"])
		.sort_values("tfidf_sum", ascending=False)
		.head(top_k)
		.copy()
	)
	if top.empty:
		raise ValueError(f"No valid rows found in {csv_path}")

	# Keep descending order so after inverting the y-axis the top-ranked term is on top.
	return top.sort_values("tfidf_sum", ascending=False)


def create_horizontal_bar_chart(
	top_df: pd.DataFrame,
	title: str,
	color: str,
	output_path: Path,
) -> None:
	sns.set_theme(style="whitegrid")
	fig, ax = plt.subplots(figsize=(10, 6))

	ax.barh(top_df["term"], top_df["tfidf_sum"], color=color)
	ax.set_title(title)
	ax.set_xlabel("TF-IDF score")
	ax.set_ylabel("Term")
	ax.invert_yaxis()

	output_path.parent.mkdir(parents=True, exist_ok=True)
	fig.tight_layout()
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def create_combined_figure(
	unigram_df: pd.DataFrame,
	bigram_df: pd.DataFrame,
	top_k: int,
	output_path: Path,
) -> None:
	sns.set_theme(style="whitegrid")
	fig, axes = plt.subplots(1, 2, figsize=(16, 8))

	axes[0].barh(unigram_df["term"], unigram_df["tfidf_sum"], color="#4C78A8")
	axes[0].set_title(f"Top {top_k} Unigrams by TF-IDF")
	axes[0].set_xlabel("TF-IDF score")
	axes[0].set_ylabel("Term")
	axes[0].invert_yaxis()

	axes[1].barh(bigram_df["term"], bigram_df["tfidf_sum"], color="#F58518")
	axes[1].set_title(f"Top {top_k} Bigrams by TF-IDF")
	axes[1].set_xlabel("TF-IDF score")
	axes[1].set_ylabel("Term")
	axes[1].invert_yaxis()

	fig.suptitle("Global TF-IDF Top Terms", fontsize=16)
	output_path.parent.mkdir(parents=True, exist_ok=True)
	fig.tight_layout(rect=(0, 0, 1, 0.97))
	fig.savefig(output_path, dpi=300, bbox_inches="tight")
	plt.close(fig)


def main() -> int:
	args = parse_args()

	unigram_df = load_top_terms(Path(args.unigrams_csv), args.top_k)
	bigram_df = load_top_terms(Path(args.bigrams_csv), args.top_k)

	out_unigrams = Path(args.out_unigrams_image)
	out_bigrams = Path(args.out_bigrams_image)
	out_combined = Path(args.out_combined_image)

	create_combined_figure(unigram_df, bigram_df, args.top_k, out_combined)
	print(f"Saved combined chart to: {out_combined.resolve()}")

	if args.skip_separate:
		return 0

	create_horizontal_bar_chart(
		unigram_df,
		title=f"Top {args.top_k} Unigrams by TF-IDF",
		color="#4C78A8",
		output_path=out_unigrams,
	)
	create_horizontal_bar_chart(
		bigram_df,
		title=f"Top {args.top_k} Bigrams by TF-IDF",
		color="#F58518",
		output_path=out_bigrams,
	)

	print(f"Saved unigram chart to: {out_unigrams.resolve()}")
	print(f"Saved bigram chart to: {out_bigrams.resolve()}")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
