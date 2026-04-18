#!/usr/bin/env python3
"""Create RQ2 plots for SKILL.md document statistics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import ScalarFormatter
import pandas as pd
import seaborn as sns


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Create RQ2 box plots for text length metrics.")
	parser.add_argument(
		"--input-jsonl",
		default="../../outputs/rq2/skill_documents.jsonl",
		help="Path to collected document dataset JSONL",
	)
	parser.add_argument(
		"--output-image",
		default="../../outputs/rq2/text_length_boxplots.png",
		help="Output path for the generated box plot image",
	)
	return parser.parse_args()


def load_lengths(input_jsonl: Path) -> pd.DataFrame:
	rows: list[dict[str, int]] = []
	with input_jsonl.open("r", encoding="utf-8") as handle:
		for line in handle:
			if not line.strip():
				continue
			doc = json.loads(line)
			text = doc.get("text", "")
			rows.append(
				{
					"word_count": len(text.split()),
					"line_count": text.count("\n") + 1,
				}
			)

	if not rows:
		raise ValueError(f"No documents found in {input_jsonl}")
	return pd.DataFrame(rows)


def summarize_distribution(values: pd.Series) -> dict[str, float]:
	q1 = float(values.quantile(0.25))
	median = float(values.quantile(0.5))
	q3 = float(values.quantile(0.75))
	iqr = q3 - q1
	lower = q1 - 1.5 * iqr
	upper = q3 + 1.5 * iqr
	outliers = int(((values < lower) | (values > upper)).sum())
	return {
		"q1": q1,
		"median": median,
		"q3": q3,
		"iqr": iqr,
		"lower_fence": lower,
		"upper_fence": upper,
		"outliers": outliers,
	}


def create_boxplots(df: pd.DataFrame, output_image: Path) -> None:
	sns.set_theme(style="whitegrid")
	fig, axes = plt.subplots(1, 2, figsize=(12, 5))

	sns.boxplot(y=df["word_count"], ax=axes[0], color="#4C78A8", showfliers=True)
	axes[0].set_title("Word Count per Document")
	axes[0].set_xlabel("")
	axes[0].set_ylabel("Words")
	axes[0].set_yscale("log")
	axes[0].set_ylim(1, float(df["word_count"].max()) * 1.05)
	axes[0].yaxis.set_major_formatter(ScalarFormatter())

	sns.boxplot(y=df["line_count"], ax=axes[1], color="#F58518", showfliers=True)
	axes[1].set_title("Line Count per Document")
	axes[1].set_xlabel("")
	axes[1].set_ylabel("Lines")
	axes[1].set_yscale("log")
	axes[1].set_ylim(1, float(df["line_count"].max()) * 1.05)
	axes[1].yaxis.set_major_formatter(ScalarFormatter())

	fig.suptitle("SKILL.md Text Length Distributions", fontsize=13, y=1.02)
	fig.tight_layout()
	output_image.parent.mkdir(parents=True, exist_ok=True)
	fig.savefig(output_image, dpi=200, bbox_inches="tight")
	plt.close(fig)


def main() -> int:
	args = parse_args()
	input_jsonl = Path(args.input_jsonl)
	output_image = Path(args.output_image)

	df = load_lengths(input_jsonl)
	create_boxplots(df, output_image)

	word_summary = summarize_distribution(df["word_count"])
	line_summary = summarize_distribution(df["line_count"])

	print(f"Saved box plot image to: {output_image.resolve()}")
	print("Word count summary:")
	print(word_summary)
	print("Line count summary:")
	print(line_summary)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
