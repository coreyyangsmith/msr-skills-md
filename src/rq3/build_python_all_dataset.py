#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

try:
    from rq3.label_processing import load_json, resolve_path, stable_tag_id, write_json
except ImportError:
    from label_processing import load_json, resolve_path, stable_tag_id, write_json


DEFAULT_A_FILE = "2026-04-19_CY_Final_Labels_A_Python.json"
DEFAULT_B_FILE = "2026-04-19_MV_Final_Labels_B_Python.json"
DEFAULT_BOTH_FILE = "2026-04-19_CY_Final_Labels_Both_Python.json"


def merge_processed_exports(
    exports: list[tuple[str, dict]],
    *,
    root_name: str = "Python_All",
    selected_both_file: str | None = None,
) -> dict:
    all_labels: dict[str, dict] = {}
    total_files = 0
    saved_at_values: list[str] = []
    combined_filter_sources: dict[str, int] = defaultdict(int)
    combined_counts: dict[str, int] = defaultdict(int)

    for source_name, data in exports:
        labels = data.get("labels", {})
        overlap = set(all_labels) & set(labels)
        if overlap:
            overlap_preview = ", ".join(sorted(list(overlap))[:5])
            raise ValueError(
                f"Overlapping documents when merging {source_name}: {overlap_preview}"
            )

        for doc_key, doc_data in labels.items():
            all_labels[doc_key] = {
                "tagIds": sorted(doc_data.get("tagIds", [])),
                **({"updatedAt": doc_data["updatedAt"]} if "updatedAt" in doc_data else {}),
            }

        dataset = data.get("dataset", {})
        total_files += int(dataset.get("totalFiles", len(labels)))
        saved_at = dataset.get("savedAt")
        if saved_at:
            saved_at_values.append(saved_at)

        processing = data.get("processing", {})
        for label, count in processing.get("filter_source_document_counts", {}).items():
            combined_filter_sources[label] += int(count)
        for key, value in processing.get("counts", {}).items():
            combined_counts[key] += int(value)

    tag_names = sorted(
        {
            tag_name
            for _, data in exports
            for tag_name in [tag.get("name") for tag in data.get("tags", [])]
            if tag_name
        }
    )
    tags = [
        {
            "id": stable_tag_id(tag_name),
            "name": tag_name,
            "createdAt": max(saved_at_values) if saved_at_values else None,
        }
        for tag_name in tag_names
    ]

    return {
        "version": 1,
        "dataset": {
            "rootName": root_name,
            "savedAt": max(saved_at_values) if saved_at_values else None,
            "totalFiles": total_files,
            "sourceFiles": [source_name for source_name, _ in exports],
            "selectedBothFile": selected_both_file,
        },
        "processing": {
            "type": "rq3-label-processing-combined",
            "filter_label": "filter",
            "combined_from": [source_name for source_name, _ in exports],
            "selected_both_file": selected_both_file,
            "filter_source_document_counts": dict(sorted(combined_filter_sources.items())),
            "counts": dict(sorted(combined_counts.items())),
        },
        "tags": tags,
        "labels": dict(sorted(all_labels.items())),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a combined processed Python_All label export from A, B, and one Both file."
    )
    parser.add_argument(
        "--processed-dir",
        default="outputs/rq3/results/processed",
        help="Directory containing processed RQ3 exports.",
    )
    parser.add_argument(
        "--a-file",
        default=DEFAULT_A_FILE,
        help="Processed Python A file to include.",
    )
    parser.add_argument(
        "--b-file",
        default=DEFAULT_B_FILE,
        help="Processed Python B file to include.",
    )
    parser.add_argument(
        "--both-file",
        default=DEFAULT_BOTH_FILE,
        help="Processed Python Both file to include once in the combined dataset.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path. Defaults to <processed-dir>/Python_All.json.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    processed_dir = resolve_path(args.processed_dir)
    output_path = (
        resolve_path(args.output)
        if args.output
        else processed_dir / "Python_All.json"
    )

    source_names = [args.a_file, args.b_file, args.both_file]
    exports: list[tuple[str, dict]] = []
    for name in source_names:
        path = processed_dir / name
        if not path.is_file():
            raise SystemExit(f"Missing processed source file: {path}")
        exports.append((name, load_json(path)))

    combined = merge_processed_exports(
        exports,
        root_name="Python_All",
        selected_both_file=args.both_file,
    )
    write_json(output_path, combined)

    print(f"Wrote {output_path}")
    print(f"Selected Both file: {args.both_file}")
    print(f"Combined documents: {len(combined['labels'])}")


if __name__ == "__main__":
    main()
