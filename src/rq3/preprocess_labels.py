#!/usr/bin/env python3
"""
Inspect and preprocess RQ3 label exports.

This script is designed as a small foundation for follow-on preprocessing.
For now it focuses on one first-class task:

1. discover the superset of labels across labeling exports in a directory

It reports both:
- raw labels exactly as stored in the JSON exports
- normalized labels after collapsing known naming inconsistencies

The JSON exports are expected to follow the schema used by the annotation
tool:

    {
      "tags": [{"id": "<uuid>", "name": "<tag>", ...}, ...],
      "labels": {
        "<doc_key>": {"tagIds": ["<uuid>", ...], ...},
        ...
      }
    }
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

try:
    from rq3.label_processing import (
        iter_label_exports,
        load_json,
        normalise_label,
        resolve_path,
        write_json,
    )
except ImportError:
    from label_processing import (
        iter_label_exports,
        load_json,
        normalise_label,
        resolve_path,
        write_json,
    )


def build_summary(paths: list[Path]) -> dict:
    raw_union: set[str] = set()
    normalized_union: set[str] = set()
    normalized_aliases: dict[str, set[str]] = defaultdict(set)
    per_file: list[dict] = []

    for path in paths:
        data = load_json(path)
        raw_tags = sorted({tag["name"].strip() for tag in data["tags"] if "name" in tag})
        normalized_tags = sorted({normalise_label(tag) for tag in raw_tags})

        raw_union.update(raw_tags)
        normalized_union.update(normalized_tags)
        for raw_tag in raw_tags:
            normalized_aliases[normalise_label(raw_tag)].add(raw_tag)

        per_file.append(
            {
                "file": path.name,
                "raw_tag_count": len(raw_tags),
                "normalized_tag_count": len(normalized_tags),
                "raw_tags": raw_tags,
                "normalized_tags": normalized_tags,
            }
        )

    alias_groups = {
        normalized: sorted(raw_values)
        for normalized, raw_values in sorted(normalized_aliases.items())
    }

    return {
        "files_processed": [path.name for path in paths],
        "file_count": len(paths),
        "raw_label_superset_count": len(raw_union),
        "raw_label_superset": sorted(raw_union),
        "normalized_label_superset_count": len(normalized_union),
        "normalized_label_superset": sorted(normalized_union),
        "normalized_alias_groups": alias_groups,
        "per_file": per_file,
    }


def render_text_report(summary: dict) -> str:
    lines = [
        "RQ3 Label Preprocessing Summary",
        "",
        f"Files processed: {summary['file_count']}",
        f"Raw label superset ({summary['raw_label_superset_count']}):",
        ", ".join(summary["raw_label_superset"]) or "(none)",
        "",
        f"Normalized label superset ({summary['normalized_label_superset_count']}):",
        ", ".join(summary["normalized_label_superset"]) or "(none)",
        "",
        "Normalization groups:",
    ]

    for normalized_label, raw_values in summary["normalized_alias_groups"].items():
        if len(raw_values) == 1 and raw_values[0] == normalized_label:
            continue
        lines.append(f"- {normalized_label}: {', '.join(raw_values)}")

    lines.append("")
    lines.append("Per-file tag counts:")
    for item in summary["per_file"]:
        lines.append(
            f"- {item['file']}: raw={item['raw_tag_count']}, normalized={item['normalized_tag_count']}"
        )

    return "\n".join(lines)

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect RQ3 labeling exports and report raw/normalized label supersets."
    )
    parser.add_argument(
        "--results-dir",
        default="outputs/rq3/results",
        help="Directory containing RQ3 result JSON files.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path for writing the summary as JSON.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    results_dir = resolve_path(args.results_dir)
    paths = iter_label_exports(results_dir)
    summary = build_summary(paths)

    print(render_text_report(summary))

    if args.output:
        output_path = resolve_path(args.output)
        write_json(output_path, summary)
        print(f"\nWrote {output_path}")


if __name__ == "__main__":
    main()
