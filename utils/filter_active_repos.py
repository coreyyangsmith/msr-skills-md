#!/usr/bin/env python3
"""Filter CSV rows to keep only isArchived=False and isFork=False. Log filter counts."""

import argparse
import sys
from pathlib import Path

import pandas as pd


def _is_false(val) -> bool:
    """Return True if value represents False (case-insensitive)."""
    if pd.isna(val):
        return False
    return str(val).lower().strip() in ("false", "0", "no", "")


def filter_csv(csv_path: Path, output_path: Path | None = None) -> pd.DataFrame:
    """Filter rows where isArchived=False and isFork=False. Log counts."""
    df = pd.read_csv(csv_path)
    total = len(df)

    # Check for required columns
    missing = [c for c in ("isArchived", "isFork") if c not in df.columns]
    if missing:
        print(f"Error: Missing columns: {missing}", file=sys.stderr)
        sys.exit(1)

    # Identify filtered rows and get repo names
    archived_mask = ~df["isArchived"].apply(_is_false)
    fork_mask = ~df["isFork"].apply(_is_false)
    archived_true = archived_mask.sum()
    fork_true = fork_mask.sum()

    repo_col = "repo" if "repo" in df.columns else df.columns[0]

    # Apply filters
    filtered = df[
        df["isArchived"].apply(_is_false) & df["isFork"].apply(_is_false)
    ].copy()
    kept = len(filtered)

    # Log
    print(f"Total rows: {total}")
    print(f"Filtered by isArchived=True: {archived_true}")
    if archived_true:
        for name in df.loc[archived_mask, repo_col].drop_duplicates().tolist():
            print(f"  - {name}")
    print(f"Filtered by isFork=True: {fork_true}")
    if fork_true:
        for name in df.loc[fork_mask, repo_col].drop_duplicates().tolist():
            print(f"  - {name}")
    print(f"Rows kept (isArchived=False and isFork=False): {kept}")

    if output_path:
        filtered.to_csv(output_path, index=False)
        print(f"Written to: {output_path}")

    return filtered


def main():
    parser = argparse.ArgumentParser(description="Filter CSV for isArchived=False, isFork=False")
    parser.add_argument("csv", type=Path, help="Path to input CSV")
    parser.add_argument("-o", "--output", type=Path, help="Path to write filtered CSV")
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"Error: File not found: {args.csv}", file=sys.stderr)
        sys.exit(1)

    filter_csv(args.csv, args.output)


if __name__ == "__main__":
    main()
