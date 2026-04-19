#!/usr/bin/env python3
"""
Process RQ3 labeling exports into a canonical form.

Processing rules
----------------
1. Normalize labels:
   - Instructive -> instructive
   - software design -> software-design
   - SE workflow management -> se-workflow-management
   - non-english -> wrong-language

2. If a skill has any of:
   - agent-skill
   - wrong-language
   - outside-scope

   then keep only a single special label for that skill. The priority is:
   wrong-language > outside-scope > agent-skill

The processed JSON files are written to a sibling /processed folder and keep
the same export-like structure so downstream scripts can consume them.
"""

from __future__ import annotations

import argparse

try:
    from rq3.label_processing import (
        build_processed_export,
        iter_label_exports,
        load_json,
        resolve_path,
        write_json,
    )
except ImportError:
    from label_processing import (
        build_processed_export,
        iter_label_exports,
        load_json,
        resolve_path,
        write_json,
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process RQ3 label exports into canonical JSON files."
    )
    parser.add_argument(
        "--results-dir",
        default="outputs/rq3/results",
        help="Directory containing the original RQ3 label JSON exports.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for processed exports. Defaults to <results-dir>/processed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    results_dir = resolve_path(args.results_dir)
    output_dir = (
        resolve_path(args.output_dir)
        if args.output_dir
        else results_dir / "processed"
    )

    paths = iter_label_exports(results_dir)
    if not paths:
        print(f"No label exports found in {results_dir}")
        return

    summary_rows: list[tuple[str, int, int, int]] = []

    for path in paths:
        data = load_json(path)
        processed = build_processed_export(data, source_name=path.name)
        output_path = output_dir / path.name
        write_json(output_path, processed)

        counts = processed["processing"]["counts"]
        summary_rows.append(
            (
                path.name,
                counts["documents"],
                counts["documents_collapsed_to_filter"],
                counts["documents_with_multiple_filter_sources"],
            )
        )
        print(f"Wrote {output_path}")

    print()
    print("Processing summary:")
    for name, docs, collapsed, conflicts in summary_rows:
        print(
            f"- {name}: documents={docs}, "
            f"collapsed_to_filter={collapsed}, multi_filter_source_conflicts={conflicts}"
        )


if __name__ == "__main__":
    main()
