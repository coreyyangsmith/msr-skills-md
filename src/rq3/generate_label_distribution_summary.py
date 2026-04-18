#!/usr/bin/env python3
"""
Generate Markdown summaries for RQ3 labeling distributions.

For each labeling JSON export, this script writes a Markdown report with:
- tag distribution (absolute counts and % of labeled files)
- score distribution, where score = number of tags assigned to a file
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

try:
    from rq3.label_processing import build_doc_label_matrix, load_json, resolve_path
except ImportError:
    from label_processing import build_doc_label_matrix, load_json, resolve_path


def pct(count: int, total: int) -> float:
    return (count / total * 100.0) if total else 0.0


def render_distribution_table(
    headers: tuple[str, ...],
    rows: list[tuple[str, ...]],
) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---:" if i else "---" for i, _ in enumerate(headers)) + " |",
    ]
    for row in rows:
        formatted = []
        for index, value in enumerate(row):
            if isinstance(value, float):
                formatted.append(f"{value:.1f}%")
            else:
                formatted.append(str(value))
        lines.append("| " + " | ".join(formatted) + " |")
    return "\n".join(lines)


def build_markdown(input_path: Path, data: dict) -> str:
    doc_labels = build_doc_label_matrix(data)
    total_files = len(doc_labels)

    tag_counts = Counter()
    score_counts = Counter()

    for labels in doc_labels.values():
        for label in labels:
            tag_counts[label] += 1
        score_counts[len(labels)] += 1

    total_tag_assignments = sum(len(labels) for labels in doc_labels.values())
    tag_rows = [
        (
            label,
            count,
            pct(count, total_files),
            pct(count, total_tag_assignments),
        )
        for label, count in sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    score_rows = [
        (str(score), count, pct(count, total_files))
        for score, count in sorted(score_counts.items())
    ]

    avg_score = total_tag_assignments / total_files if total_files else 0.0

    raw_tag_names = sorted({tag["name"] for tag in data["tags"]})
    normalised_tag_names = sorted(tag_counts)

    return "\n".join(
        [
            f"# {input_path.stem} Summary",
            "",
            "## Dataset",
            f"- Source file: `{input_path.name}`",
            f"- Saved at: `{data['dataset'].get('savedAt', 'unknown')}`",
            f"- Dataset root: `{data['dataset'].get('rootName', 'unknown')}`",
            f"- Total labeled files: {total_files}",
            f"- Total normalized tag assignments: {total_tag_assignments}",
            f"- Average score (tags per file): {avg_score:.2f}",
            "",
            "## Notes",
            "- `% of files` is calculated over all labeled files in the dataset.",
            "- `% of tag assignments` is calculated over all normalized tag assignments in the dataset.",
            "- Score is defined here as the number of tags assigned to a file.",
            "- Tag names are normalized for comparability across exports.",
            f"- Raw tags in export ({len(raw_tag_names)}): {', '.join(f'`{name}`' for name in raw_tag_names)}",
            f"- Normalized tags used in this summary ({len(normalised_tag_names)}): {', '.join(f'`{name}`' for name in normalised_tag_names)}",
            "",
            "## Tag Distribution",
            render_distribution_table(
                ("Tag", "Count", "% of Files", "% of Tag Assignments"),
                tag_rows,
            ),
            "",
            "## Score Distribution",
            render_distribution_table(("Score", "Count", "% of Files"), score_rows),
            "",
        ]
    )


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_distribution_summary.md")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Markdown summaries for CY label distributions."
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        help="One or more label JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for generated Markdown summaries.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = resolve_path(args.output_dir) if args.output_dir else None

    for input_arg in args.inputs:
        input_path = resolve_path(input_arg)
        data = load_json(input_path)
        markdown = build_markdown(input_path, data)

        if output_dir is None:
            output_path = default_output_path(input_path)
        else:
            output_path = output_dir / f"{input_path.stem}_distribution_summary.md"

        write_text(output_path, markdown)
        print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
