#!/usr/bin/env python3
"""Check whether moved repos appear in RQ3 labeling_samples/Python.

Reads moved repos from outputs/raw_data_filtered_out/moved_repos.tsv and checks
if those repos are present in outputs/rq3/labeling_samples/Python (A, B, both).
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Set


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MOVED_TSV = REPO_ROOT / "outputs/raw_data_filtered_out/moved_repos.tsv"
DEFAULT_LABELING_DIR = REPO_ROOT / "outputs/rq3/labeling_samples/Python"
DEFAULT_REPORT = REPO_ROOT / "outputs/raw_data_filtered_out/moved_repos_in_labeling_samples_python.tsv"
DEFAULT_OVERLAP_CSV = REPO_ROOT / "outputs/raw_data_filtered_out/removed_repos_in_python_labeling_samples.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check overlap between moved repos and RQ3 labeling_samples/Python repos."
    )
    parser.add_argument(
        "--moved-tsv",
        default=str(DEFAULT_MOVED_TSV),
        help="Path to moved_repos.tsv",
    )
    parser.add_argument(
        "--labeling-dir",
        default=str(DEFAULT_LABELING_DIR),
        help="Path to outputs/rq3/labeling_samples/Python",
    )
    parser.add_argument(
        "--report-tsv",
        default=str(DEFAULT_REPORT),
        help="Output TSV report path",
    )
    parser.add_argument(
        "--overlap-csv",
        default=str(DEFAULT_OVERLAP_CSV),
        help=(
            "CSV path for overlaps only (removed repos present in Python labeling "
            "samples), with subfolder column A/B/both."
        ),
    )
    return parser.parse_args()


def _resolve_labeling_dir(path: Path) -> Path:
    """Handle common typo 'labeling_smaples' by auto-correcting when needed."""
    if path.exists() and path.is_dir():
        return path

    corrected = Path(str(path).replace("labeling_smaples", "labeling_samples"))
    if corrected.exists() and corrected.is_dir():
        return corrected

    raise FileNotFoundError(f"Labeling directory not found: {path}")


def read_moved_repos(moved_tsv: Path) -> Dict[str, Dict[str, str]]:
    """Return mapping repo -> metadata from moved_repos.tsv."""
    if not moved_tsv.exists() or not moved_tsv.is_file():
        raise FileNotFoundError(f"Moved TSV not found: {moved_tsv}")

    out: Dict[str, Dict[str, str]] = {}
    with moved_tsv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        required = {"repo", "dir_name", "reason", "action"}
        if not required.issubset(set(reader.fieldnames or [])):
            raise ValueError(
                f"Moved TSV is missing required columns {sorted(required)}; "
                f"found {reader.fieldnames}"
            )

        for row in reader:
            repo = (row.get("repo") or "").strip()
            if not repo:
                continue
            out[repo] = {
                "dir_name": (row.get("dir_name") or "").strip(),
                "reason": (row.get("reason") or "").strip(),
                "action": (row.get("action") or "").strip(),
            }
    return out


def collect_labeling_repo_dirs(labeling_dir: Path) -> Dict[str, Set[str]]:
    """Collect repo dir names from A/B/both buckets."""
    buckets = ["A", "B", "both"]
    found: Dict[str, Set[str]] = {b: set() for b in buckets}

    for bucket in buckets:
        bucket_dir = labeling_dir / bucket
        if not bucket_dir.exists() or not bucket_dir.is_dir():
            continue
        for child in bucket_dir.iterdir():
            if child.is_dir():
                found[bucket].add(child.name)

    return found


def repo_to_dir_name(repo: str) -> str:
    owner, name = repo.split("/", 1)
    return f"{owner}__{name}"


def write_report(report_tsv: Path, rows: list[dict[str, str]]) -> None:
    report_tsv.parent.mkdir(parents=True, exist_ok=True)
    with report_tsv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["repo", "dir_name", "reason", "action", "in_A", "in_B", "in_both", "present_anywhere"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(rows)


def pick_subfolder(in_a: bool, in_b: bool, in_both: bool) -> str:
    if in_both:
        return "both"
    if in_a:
        return "A"
    if in_b:
        return "B"
    return ""


def write_overlap_csv(overlap_csv: Path, rows: list[dict[str, str]]) -> int:
    overlap_rows: list[dict[str, str]] = []
    for row in rows:
        if row["present_anywhere"] != "1":
            continue
        in_a = row["in_A"] == "1"
        in_b = row["in_B"] == "1"
        in_both = row["in_both"] == "1"
        overlap_rows.append(
            {
                "repo": row["repo"],
                "subfolder": pick_subfolder(in_a, in_b, in_both),
                "reason": row["reason"],
                "action": row["action"],
            }
        )

    overlap_csv.parent.mkdir(parents=True, exist_ok=True)
    with overlap_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["repo", "subfolder", "reason", "action"])
        writer.writeheader()
        writer.writerows(overlap_rows)
    return len(overlap_rows)


def main() -> int:
    args = parse_args()

    moved_tsv = Path(args.moved_tsv).resolve()
    labeling_dir = _resolve_labeling_dir(Path(args.labeling_dir).resolve())
    report_tsv = Path(args.report_tsv).resolve()
    overlap_csv = Path(args.overlap_csv).resolve()

    moved = read_moved_repos(moved_tsv)
    labeling = collect_labeling_repo_dirs(labeling_dir)

    rows: list[dict[str, str]] = []
    present_count = 0

    for repo, meta in sorted(moved.items()):
        dir_name = meta["dir_name"] or repo_to_dir_name(repo)
        in_a = dir_name in labeling["A"]
        in_b = dir_name in labeling["B"]
        in_both = dir_name in labeling["both"]
        present_anywhere = in_a or in_b or in_both
        if present_anywhere:
            present_count += 1

        rows.append(
            {
                "repo": repo,
                "dir_name": dir_name,
                "reason": meta["reason"],
                "action": meta["action"],
                "in_A": "1" if in_a else "0",
                "in_B": "1" if in_b else "0",
                "in_both": "1" if in_both else "0",
                "present_anywhere": "1" if present_anywhere else "0",
            }
        )

    write_report(report_tsv, rows)
    overlap_count = write_overlap_csv(overlap_csv, rows)

    total = len(rows)
    print("Moved repos vs labeling_samples/Python")
    print(f"  moved repos checked: {total}")
    print(f"  present in labeling samples: {present_count}")
    print(f"  absent from labeling samples: {total - present_count}")
    print(f"  report: {report_tsv}")
    print(f"  overlap csv: {overlap_csv} ({overlap_count} rows)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
