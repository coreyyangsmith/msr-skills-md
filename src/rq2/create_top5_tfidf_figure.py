#!/usr/bin/env python3
"""Generate the Top 5 RQ2 unigram/bigram figures, one per corpus (full, deduplicated).

Bars show summed TF-IDF; labels add the share of skills and repositories whose
name + description (the TF-IDF corpus) contain the term.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, CountVectorizer

from rq2.analyze_tfidf_sklearn import CUSTOM_STOPWORDS, build_corpus_streaming
from rq2.create_comparison_diagram import (
    DEFAULT_LEFT_BIGRAMS,
    DEFAULT_LEFT_UNIGRAMS,
    DEFAULT_RIGHT_BIGRAMS,
    DEFAULT_RIGHT_UNIGRAMS,
    REPO_ROOT,
    UNIGRAM_COLOR,
    _draw_ranked_bars,
    _setup_style,
    load_top_terms,
)

DEFAULT_FULL_OUT = REPO_ROOT / "outputs/rq2/top5_unigrams_bigrams_full.png"
DEFAULT_DEDUP_OUT = REPO_ROOT / "outputs/rq2/top5_unigrams_bigrams_dedup.png"
DEFAULT_FULL_DOCS = REPO_ROOT / "outputs/rq2/skill_documents.jsonl"
DEFAULT_DEDUP_DOCS = REPO_ROOT / "outputs/rq2/skill_documents_dedup.jsonl"
STOPWORDS = sorted(set(ENGLISH_STOP_WORDS).union(CUSTOM_STOPWORDS))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the Top 5 RQ2 TF-IDF figures.")
    parser.add_argument("--full-unigrams", type=Path, default=DEFAULT_LEFT_UNIGRAMS)
    parser.add_argument("--full-bigrams", type=Path, default=DEFAULT_LEFT_BIGRAMS)
    parser.add_argument("--dedup-unigrams", type=Path, default=DEFAULT_RIGHT_UNIGRAMS)
    parser.add_argument("--dedup-bigrams", type=Path, default=DEFAULT_RIGHT_BIGRAMS)
    parser.add_argument("--full-docs", type=Path, default=DEFAULT_FULL_DOCS)
    parser.add_argument("--dedup-docs", type=Path, default=DEFAULT_DEDUP_DOCS)
    parser.add_argument("--full-out", type=Path, default=DEFAULT_FULL_OUT)
    parser.add_argument("--dedup-out", type=Path, default=DEFAULT_DEDUP_OUT)
    parser.add_argument("--fig-width", type=float, default=13.0)
    parser.add_argument("--fig-height", type=float, default=2.6)
    parser.add_argument("--bar-height", type=float, default=0.35)
    parser.add_argument("--bar-step", type=float, default=0.40)
    parser.add_argument("--column-space", type=float, default=0.34)
    parser.add_argument("--color", default=UNIGRAM_COLOR)
    parser.add_argument("--dpi", type=int, default=300)
    return parser.parse_args(argv)


def term_coverage(rows: list[dict], corpus: list[str], terms: list[str], ngram: int) -> list[dict]:
    """Per term: skills and repos whose TF-IDF text contains it (same tokenization and stop words)."""
    matrix = CountVectorizer(
        vocabulary=terms, binary=True, stop_words=STOPWORDS, ngram_range=(ngram, ngram)
    ).fit_transform(corpus).tocsc()
    repos = [row["repo"] for row in rows]
    total_repos = len(set(repos))
    out = []
    for i, term in enumerate(terms):
        doc_idx = matrix[:, i].nonzero()[0]
        by_repo = Counter(repos[j] for j in doc_idx)
        top_repo, top_count = by_repo.most_common(1)[0] if by_repo else ("", 0)
        out.append({
            "term": term,
            "skills": len(doc_idx),
            "pct_skills": 100 * len(doc_idx) / len(corpus),
            "repos": len(by_repo),
            "pct_repos": 100 * len(by_repo) / total_repos,
            "top_repo": top_repo,
            "pct_skills_from_top_repo": 100 * top_count / len(doc_idx) if len(doc_idx) else 0.0,
        })
    return out


def plot_corpus(unigrams_csv: Path, bigrams_csv: Path, docs_jsonl: Path, out_path: Path, args) -> None:
    rows, corpus, _, _ = build_corpus_streaming(docs_jsonl, None)
    _setup_style()
    fig, axes = plt.subplots(1, 2, figsize=(args.fig_width, args.fig_height))
    coverage_rows = []
    panels = [(axes[0], unigrams_csv, "(a) Unigrams", 1), (axes[1], bigrams_csv, "(b) Bigrams", 2)]
    for ax, csv_path, title, ngram in panels:
        terms, scores = load_top_terms(csv_path, 5)
        coverage = term_coverage(rows, corpus, terms, ngram)
        labels = [f"{s:,.0f}  ({c['pct_skills']:.1f}% skills, {c['pct_repos']:.1f}% repos)"
                  for s, c in zip(scores, coverage)]
        _draw_ranked_bars(ax, terms, scores, args.color, title, bar_height=args.bar_height,
                          bar_step=args.bar_step, value_labels=labels, x_headroom=1.75)
        coverage_rows += [{"ngram": ngram, "tfidf_sum": s, **c} for s, c in zip(scores, coverage)]
    fig.subplots_adjust(left=0.16, right=0.98, wspace=args.column_space)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=args.dpi, bbox_inches="tight", pad_inches=0.08)
    plt.close(fig)

    csv_out = out_path.with_name(out_path.stem + "_coverage.csv")
    with csv_out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(coverage_rows[0]))
        writer.writeheader()
        writer.writerows(coverage_rows)
    print(f"Saved: {out_path}\nSaved: {csv_out} (skills in corpus: {len(corpus)})")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    plot_corpus(args.full_unigrams, args.full_bigrams, args.full_docs, args.full_out, args)
    plot_corpus(args.dedup_unigrams, args.dedup_bigrams, args.dedup_docs, args.dedup_out, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
