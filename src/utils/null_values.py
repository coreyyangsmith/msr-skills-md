#!/usr/bin/env python3
"""
null_values.py

Read a CSV and report statistics and counts of null/empty values across all columns.
Treats empty strings, whitespace-only strings, and missing fields as null.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


def is_null(value: str | None) -> bool:
    """Return True if the value is considered null (empty or whitespace-only)."""
    if value is None:
        return True
    return not value.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Report null/empty value counts and statistics for each column in a CSV."
    )
    parser.add_argument(
        "csv",
        type=str,
        help="Path to the CSV file",
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="Treat first row as data (no header); columns will be named col_0, col_1, ...",
    )
    parser.add_argument(
        "--delimiter",
        default=",",
        help="Field delimiter (default: ',')",
    )
    args = parser.parse_args(argv)

    path = Path(args.csv)
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        return 1
    if not path.is_file():
        print(f"Error: not a file: {path}", file=sys.stderr)
        return 1

    with open(path, "r", newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=args.delimiter)
        if args.no_header:
            first = next(reader, None)
            if first is None:
                print("Error: CSV is empty", file=sys.stderr)
                return 1
            columns = [f"col_{i}" for i in range(len(first))]
            total_rows = 1
            null_counts = {c: 0 for c in columns}
            for i, val in enumerate(first):
                if i < len(columns) and is_null(val):
                    null_counts[columns[i]] += 1
        else:
            header = next(reader, None)
            if header is None:
                print("Error: CSV is empty", file=sys.stderr)
                return 1
            columns = header
            null_counts = {c: 0 for c in columns}
            total_rows = 0
            for row in reader:
                total_rows += 1
                for i, col in enumerate(columns):
                    val = row[i] if i < len(row) else ""
                    if is_null(val):
                        null_counts[col] += 1

    # Summary
    print(f"File: {path}")
    print(f"Rows: {total_rows}")
    print(f"Columns: {len(columns)}")
    print()

    if total_rows == 0:
        print("No data rows.")
        return 0

    # Per-column stats
    max_col_len = max(len(c) for c in columns) if columns else 0
    max_col_len = max(max_col_len, len("Column"))

    header_fmt = f"  {{:<{max_col_len}}}  {{:>10}}  {{:>10}}  {{:>8}}"
    row_fmt = f"  {{:<{max_col_len}}}  {{:>10}}  {{:>10}}  {{:>7.2f}}%"

    print(header_fmt.format("Column", "Null count", "Non-null", "% null"))
    print("  " + "-" * (max_col_len + 10 + 10 + 8 + 4))

    total_nulls = 0
    for col in columns:
        n = null_counts[col]
        total_nulls += n
        pct = 100.0 * n / total_rows if total_rows else 0
        non_null = total_rows - n
        print(row_fmt.format(col, n, non_null, pct))

    print("  " + "-" * (max_col_len + 10 + 10 + 8 + 4))
    total_cells = total_rows * len(columns) if columns else 0
    overall_pct = 100.0 * total_nulls / total_cells if total_cells else 0
    non_null_cells = total_cells - total_nulls
    print(header_fmt.format("(all columns)", total_nulls, non_null_cells, f"{overall_pct:.2f}%"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
