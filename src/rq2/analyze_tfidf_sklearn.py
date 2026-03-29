#!/usr/bin/env python3
"""Run TF-IDF on SKILL.md frontmatter (name + description) from collected JSONL/JSON documents."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

log = logging.getLogger(__name__)

FRONTMATTER_BOUNDARY_RE = re.compile(r"^---\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^(name|description):\s*(.*)$", re.MULTILINE)

CUSTOM_STOPWORDS = {
    "use",
    "using",
    "used",
    "create",
    "creates",
    "creating",
    "new",
    "data",
    "user",
    "code",
    "project",
    "skill",
    "analysis",
    "design",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TF-IDF analysis on SKILL.md frontmatter (name + description) from collected documents."
    )
    parser.add_argument(
        "--input",
        default="../../outputs/rq2/skill_documents.jsonl",
        help="Path to input JSONL/JSON file with documents containing a 'text' field",
    )
    parser.add_argument(
        "--out-global",
        default="../../outputs/rq2/tfidf_sklearn_top_terms_global.csv",
        help="CSV output for top global TF-IDF terms",
    )
    parser.add_argument(
        "--out-per-doc",
        default="../../outputs/rq2/tfidf_sklearn_top_terms_per_document.csv",
        help="CSV output for top TF-IDF terms per document",
    )
    parser.add_argument(
        "--out-summary",
        default="../../outputs/rq2/tfidf_sklearn_summary.json",
        help="JSON output for run summary",
    )
    parser.add_argument("--max-features", type=int, default=10000, help="Max vocabulary size for TF-IDF")
    parser.add_argument("--min-df", type=int, default=2, help="Ignore terms appearing in fewer docs than this")
    parser.add_argument("--max-df", type=float, default=0.9, help="Ignore terms appearing in more docs than this ratio")
    parser.add_argument("--top-k-global", type=int, default=200, help="Top global terms to write")
    parser.add_argument("--top-k-per-doc", type=int, default=30, help="Top terms per document to write")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser.parse_args(argv)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        return value[1:-1].strip()
    return value


def extract_name_description(markdown_text: str) -> tuple[str, str]:
    boundaries = list(FRONTMATTER_BOUNDARY_RE.finditer(markdown_text))
    if len(boundaries) < 2:
        return "", ""

    start = boundaries[0].end()
    end = boundaries[1].start()
    frontmatter = markdown_text[start:end]

    values: dict[str, str] = {"name": "", "description": ""}
    for match in FIELD_RE.finditer(frontmatter):
        key = match.group(1)
        raw_value = match.group(2)
        values[key] = _strip_quotes(raw_value)

    return values["name"], values["description"]


def parse_documents(input_path: Path) -> list[dict[str, Any]]:
    raw = input_path.read_text(encoding="utf-8")

    stripped = raw.lstrip()
    if stripped.startswith("["):
        payload = json.loads(raw)
        if not isinstance(payload, list):
            raise ValueError("JSON input must be a list of objects")
        docs = [item for item in payload if isinstance(item, dict)]
    else:
        docs = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            if isinstance(item, dict):
                docs.append(item)

    return docs


def build_corpus(documents: list[dict[str, Any]]) -> tuple[list[dict[str, str]], list[str]]:
    rows: list[dict[str, str]] = []
    corpus: list[str] = []

    for idx, doc in enumerate(documents):
        text = str(doc.get("text", "") or "")
        name, description = extract_name_description(text)
        joined = f"{name} {description}".strip()

        if not joined:
            continue

        rows.append(
            {
                "doc_id": str(idx),
                "language": str(doc.get("language", "")),
                "repo": str(doc.get("repo", "")),
                "relative_path": str(doc.get("relative_path", "")),
                "name": name,
                "description": description,
                "name_description": joined,
            }
        )
        corpus.append(joined)

    return rows, corpus


def write_global_terms(path: Path, feature_names: list[str], global_scores: list[float], top_k: int) -> None:
    pairs = sorted(zip(feature_names, global_scores), key=lambda x: x[1], reverse=True)[:top_k]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["term", "tfidf_sum"])
        writer.writerows(pairs)


def write_per_doc_terms(
    path: Path,
    rows: list[dict[str, str]],
    matrix: Any,
    feature_names: list[str],
    top_k: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "doc_id",
                "language",
                "repo",
                "relative_path",
                "term_rank",
                "term",
                "tfidf",
                "name",
                "description",
            ]
        )

        for row_idx, row_meta in enumerate(rows):
            vec = matrix.getrow(row_idx)
            if vec.nnz == 0:
                continue

            ranked = sorted(zip(vec.indices, vec.data), key=lambda x: x[1], reverse=True)[:top_k]
            for rank, (term_idx, score) in enumerate(ranked, start=1):
                writer.writerow(
                    [
                        row_meta["doc_id"],
                        row_meta["language"],
                        row_meta["repo"],
                        row_meta["relative_path"],
                        rank,
                        feature_names[term_idx],
                        float(score),
                        row_meta["name"],
                        row_meta["description"],
                    ]
                )


def write_summary(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    input_path = Path(args.input)
    if not input_path.exists() or not input_path.is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    documents = parse_documents(input_path)
    rows, corpus = build_corpus(documents)

    if not corpus:
        raise ValueError("No documents with non-empty 'name + description' were found in input")

    combined_stopwords = sorted(set(ENGLISH_STOP_WORDS).union(CUSTOM_STOPWORDS))

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words=combined_stopwords,
        ngram_range=(2, 2),
        max_features=args.max_features,
        min_df=args.min_df,
        max_df=args.max_df,
    )
    matrix = vectorizer.fit_transform(corpus)
    feature_names = vectorizer.get_feature_names_out().tolist()

    global_scores = matrix.sum(axis=0).A1.tolist()

    out_global = Path(args.out_global)
    out_per_doc = Path(args.out_per_doc)
    out_summary = Path(args.out_summary)

    write_global_terms(out_global, feature_names, global_scores, args.top_k_global)
    write_per_doc_terms(out_per_doc, rows, matrix, feature_names, args.top_k_per_doc)

    summary = {
        "input_path": str(input_path.resolve()),
        "documents_total_in_input": len(documents),
        "documents_used_for_tfidf": len(corpus),
        "vocabulary_size": len(feature_names),
        "matrix_shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        "params": {
            "ngram_range": [2, 2],
            "custom_stopwords": sorted(CUSTOM_STOPWORDS),
            "max_features": args.max_features,
            "min_df": args.min_df,
            "max_df": args.max_df,
            "top_k_global": args.top_k_global,
            "top_k_per_doc": args.top_k_per_doc,
        },
        "outputs": {
            "global_terms_csv": str(out_global.resolve()),
            "per_document_terms_csv": str(out_per_doc.resolve()),
        },
    }
    write_summary(out_summary, summary)

    print(f"Processed {len(corpus)} documents for TF-IDF")
    print(f"Vocabulary size: {len(feature_names)}")
    print(f"- global terms: {out_global.resolve()}")
    print(f"- per-doc terms: {out_per_doc.resolve()}")
    print(f"- summary: {out_summary.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
