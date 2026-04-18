#!/usr/bin/env python3
"""
Analyze processed RQ3 label exports and write summary statistics.

The report focuses on:
- processed vs filtered documents
- SDLC-related category distributions
- instruction-type distributions
- instruction-type x SDLC group co-occurrence
"""

from __future__ import annotations

import argparse
from collections import Counter

try:
    from rq3.label_processing import (
        FILTER_LABEL,
        INSTRUCTION_TYPE_LABELS,
        SDLC_STAGE_LABELS,
        build_doc_label_matrix,
        iter_label_exports,
        load_json,
        resolve_path,
        write_json,
    )
except ImportError:
    from label_processing import (
        FILTER_LABEL,
        INSTRUCTION_TYPE_LABELS,
        SDLC_STAGE_LABELS,
        build_doc_label_matrix,
        iter_label_exports,
        load_json,
        resolve_path,
        write_json,
    )


def pct(count: int, total: int) -> float:
    return (count / total * 100.0) if total else 0.0


def split_filtered_docs(
    doc_labels: dict[str, set[str]],
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    filtered = {
        doc: labels
        for doc, labels in doc_labels.items()
        if FILTER_LABEL in labels
    }
    retained = {
        doc: labels
        for doc, labels in doc_labels.items()
        if FILTER_LABEL not in labels
    }
    return retained, filtered


def label_distribution(doc_labels: dict[str, set[str]]) -> dict[str, dict[str, float | int]]:
    total_docs = len(doc_labels)
    counts = Counter()
    for labels in doc_labels.values():
        counts.update(labels)

    return {
        label: {
            "count": count,
            "pct_docs": round(pct(count, total_docs), 2),
        }
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    }


def score_distribution(doc_labels: dict[str, set[str]]) -> dict[str, dict[str, float | int]]:
    total_docs = len(doc_labels)
    counts = Counter(len(labels) for labels in doc_labels.values())
    return {
        str(score): {
            "count": count,
            "pct_docs": round(pct(count, total_docs), 2),
        }
        for score, count in sorted(counts.items())
    }


def average_labels(doc_labels: dict[str, set[str]]) -> float:
    if not doc_labels:
        return 0.0
    return round(
        sum(len(labels) for labels in doc_labels.values()) / len(doc_labels),
        3,
    )


def docs_with_any(doc_labels: dict[str, set[str]], label_set: set[str] | frozenset[str]) -> int:
    return sum(1 for labels in doc_labels.values() if labels & label_set)


def instruction_distribution(
    doc_labels: dict[str, set[str]],
) -> dict[str, dict[str, float | int]]:
    total_docs = len(doc_labels)
    return {
        label: {
            "count": count,
            "pct_docs": round(pct(count, total_docs), 2),
        }
        for label in INSTRUCTION_TYPE_LABELS
        if (count := sum(1 for labels in doc_labels.values() if label in labels)) > 0
    }


def sdlc_stage_distribution(
    doc_labels: dict[str, set[str]],
) -> dict[str, dict[str, float | int]]:
    total_docs = len(doc_labels)
    output: dict[str, dict[str, float | int]] = {}
    for stage in SDLC_STAGE_LABELS:
        count = sum(1 for labels in doc_labels.values() if stage in labels)
        if count:
            output[stage] = {
                "count": count,
                "pct_docs": round(pct(count, total_docs), 2),
            }
    return output


def instruction_sdlc_matrix(
    doc_labels: dict[str, set[str]],
) -> dict[str, dict[str, int]]:
    matrix: dict[str, dict[str, int]] = {}
    for instruction in INSTRUCTION_TYPE_LABELS:
        row: dict[str, int] = {}
        for stage in SDLC_STAGE_LABELS:
            count = sum(
                1
                for labels in doc_labels.values()
                if instruction in labels and stage in labels
            )
            if count:
                row[stage] = count
        if row:
            matrix[instruction] = row
    return matrix


def summarize_dataset(path):
    data = load_json(path)
    doc_labels = build_doc_label_matrix(data, normalise=False)
    retained, filtered = split_filtered_docs(doc_labels)
    instruction_set = set(INSTRUCTION_TYPE_LABELS)
    sdlc_stage_set = set(SDLC_STAGE_LABELS)
    processing = data.get("processing", {})

    return {
        "file": path.name,
        "dataset_root": data.get("dataset", {}).get("rootName"),
        "total_documents": len(doc_labels),
        "filtered_documents": len(filtered),
        "filtered_pct": round(pct(len(filtered), len(doc_labels)), 2),
        "retained_documents": len(retained),
        "retained_pct": round(pct(len(retained), len(doc_labels)), 2),
        "average_labels_per_document": average_labels(doc_labels),
        "average_labels_per_retained_document": average_labels(retained),
        "average_labels_per_filtered_document": average_labels(filtered),
        "filter_source_document_counts": processing.get("filter_source_document_counts", {}),
        "documents_with_any_instruction_type": docs_with_any(doc_labels, instruction_set),
        "documents_with_any_sdlc_label": docs_with_any(doc_labels, sdlc_stage_set),
        "documents_with_instruction_and_sdlc": sum(
            1
            for labels in doc_labels.values()
            if labels & instruction_set and labels & sdlc_stage_set
        ),
        "label_distribution_all": label_distribution(doc_labels),
        "label_distribution_retained": label_distribution(retained),
        "label_distribution_filtered": label_distribution(filtered),
        "score_distribution_all": score_distribution(doc_labels),
        "score_distribution_retained": score_distribution(retained),
        "score_distribution_filtered": score_distribution(filtered),
        "instruction_type_distribution_all": instruction_distribution(doc_labels),
        "instruction_type_distribution_retained": instruction_distribution(retained),
        "sdlc_stage_distribution_all": sdlc_stage_distribution(doc_labels),
        "sdlc_stage_distribution_retained": sdlc_stage_distribution(retained),
        "instruction_x_sdlc_stage_retained": instruction_sdlc_matrix(retained),
    }


def render_markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    if not rows:
        return "_No data_"

    align = ["---"] + ["---:" for _ in headers[1:]]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(align) + " |",
    ]
    for row in rows:
        formatted = []
        for value in row:
            if isinstance(value, float):
                formatted.append(f"{value:.2f}")
            else:
                formatted.append(str(value))
        lines.append("| " + " | ".join(formatted) + " |")
    return "\n".join(lines)


def render_distribution_rows(distribution: dict[str, dict[str, float | int]]) -> list[list[object]]:
    return [
        [label, stats["count"], stats["pct_docs"]]
        for label, stats in distribution.items()
    ]


def build_markdown_report(summaries: list[dict]) -> str:
    overview_rows = [
        [
            summary["file"],
            summary["total_documents"],
            summary["retained_documents"],
            summary["filtered_documents"],
            summary["filtered_pct"],
            summary["documents_with_any_sdlc_label"],
            summary["documents_with_any_instruction_type"],
        ]
        for summary in summaries
    ]

    lines = [
        "# Processed RQ3 Label Statistics",
        "",
        "Processed vs filtered comparisons are document-level, not repo-level.",
        "",
        "## Overview",
        render_markdown_table(
            [
                "File",
                "Docs",
                "Retained",
                "Filtered",
                "Filtered %",
                "Any SDLC",
                "Any Instruction",
            ],
            overview_rows,
        ),
    ]

    for summary in summaries:
        lines.extend(
            [
                "",
                f"## {summary['file']}",
                "",
                f"- Dataset root: `{summary['dataset_root']}`",
                f"- Total documents: {summary['total_documents']}",
                f"- Retained documents: {summary['retained_documents']} ({summary['retained_pct']:.2f}%)",
                f"- Filtered documents: {summary['filtered_documents']} ({summary['filtered_pct']:.2f}%)",
                f"- Avg labels / doc: {summary['average_labels_per_document']:.3f}",
                f"- Avg labels / retained doc: {summary['average_labels_per_retained_document']:.3f}",
                f"- Avg labels / filtered doc: {summary['average_labels_per_filtered_document']:.3f}",
                f"- Filter source counts: `{summary['filter_source_document_counts']}`",
                "",
                "### Label Distribution (Retained)",
                render_markdown_table(
                    ["Label", "Count", "% Docs"],
                    render_distribution_rows(summary["label_distribution_retained"]),
                ),
                "",
                "### Label Distribution (Filtered)",
                render_markdown_table(
                    ["Label", "Count", "% Docs"],
                    render_distribution_rows(summary["label_distribution_filtered"]),
                ),
                "",
                "### Instruction Type Distribution (All)",
                render_markdown_table(
                    ["Instruction Type", "Count", "% Docs"],
                    render_distribution_rows(summary["instruction_type_distribution_all"]),
                ),
                "",
                "### SDLC Stage Distribution (Retained)",
                render_markdown_table(
                    ["SDLC Stage", "Count", "% Docs"],
                    render_distribution_rows(summary["sdlc_stage_distribution_retained"]),
                ),
                "",
                "### Instruction x SDLC Stage (Retained)",
                render_markdown_table(
                    ["Instruction Type", "SDLC Stage", "Count"],
                    [
                        [instruction, stage, count]
                        for instruction, row in summary["instruction_x_sdlc_stage_retained"].items()
                        for stage, count in row.items()
                    ],
                ),
            ]
        )

    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate statistics and distributions for processed RQ3 label exports."
    )
    parser.add_argument(
        "--input-dir",
        default="outputs/rq3/results/processed",
        help="Directory containing processed label exports.",
    )
    parser.add_argument(
        "--output-json",
        default=None,
        help="Optional path for the JSON statistics report.",
    )
    parser.add_argument(
        "--output-md",
        default=None,
        help="Optional path for the Markdown statistics report.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    input_dir = resolve_path(args.input_dir)
    paths = iter_label_exports(input_dir)

    if not paths:
        print(f"No processed label exports found in {input_dir}")
        return

    summaries = [summarize_dataset(path) for path in paths]
    report = {"datasets": summaries}
    markdown = build_markdown_report(summaries)

    output_json = (
        resolve_path(args.output_json)
        if args.output_json
        else input_dir / "processed_label_statistics.json"
    )
    output_md = (
        resolve_path(args.output_md)
        if args.output_md
        else input_dir / "processed_label_statistics.md"
    )

    write_json(output_json, report)
    output_md.write_text(markdown, encoding="utf-8")

    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")


if __name__ == "__main__":
    main()
