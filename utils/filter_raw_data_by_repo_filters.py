#!/usr/bin/env python3
"""Filter outputs/raw_data folders using shared repo filters.

The script applies the same blacklist + repo-name filter words used by the
pipeline and moves excluded repo folders to a separate output location.
"""

from __future__ import annotations

import argparse
import csv
import shutil
from collections import Counter
from pathlib import Path
import sys
from typing import Iterable


# Allow importing shared filters from src/ when this script is run from anywhere.
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from filters import REPO_NAME_FILTER_WORDS, is_repo_excluded, load_blacklist  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply shared repo filters to raw_data folder structure and move "
            "excluded repo directories to a filtered-out folder."
        )
    )
    parser.add_argument(
        "--raw-data-dir",
        default=str(REPO_ROOT / "outputs/raw_data"),
        help="Path to raw_data root (default: outputs/raw_data)",
    )
    parser.add_argument(
        "--filtered-out-dir",
        default=str(REPO_ROOT / "outputs/raw_data_filtered_out"),
        help="Where excluded repo folders are moved (default: outputs/raw_data_filtered_out)",
    )
    parser.add_argument(
        "--blacklist",
        default=str(REPO_ROOT / "blacklist.txt"),
        help="Path to blacklist file (default: blacklist.txt)",
    )
    parser.add_argument(
        "--report-tsv",
        default="",
        help=(
            "TSV report path. Defaults to <filtered-out-dir>/moved_repos.tsv "
            "(or dry_run_repos.tsv in dry-run mode)."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually move directories. Without this flag, runs as dry-run.",
    )
    return parser.parse_args()


def decode_repo_from_dir(dir_name: str) -> str | None:
    """Convert owner__repo directory names back to owner/repo."""
    if "__" not in dir_name:
        return None
    owner, repo = dir_name.split("__", 1)
    if not owner or not repo:
        return None
    return f"{owner}/{repo}"


def iter_repo_dirs(raw_data_dir: Path) -> Iterable[tuple[str, Path]]:
    """Yield (language, repo_dir_path) for each repo directory in raw_data."""
    for language_dir in sorted(p for p in raw_data_dir.iterdir() if p.is_dir()):
        language = language_dir.name
        for repo_dir in sorted(p for p in language_dir.iterdir() if p.is_dir()):
            yield language, repo_dir


def ensure_unique_target(path: Path) -> Path:
    """Return a non-colliding target path by adding suffixes when needed."""
    if not path.exists():
        return path
    for i in range(1, 10000):
        candidate = path.with_name(f"{path.name}__dup{i}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"Could not find unique target path for {path}")


def write_report(report_path: Path, rows: list[dict[str, str]]) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["repo", "language", "dir_name", "reason", "src", "dst", "action"],
            delimiter="\t",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()

    raw_data_dir = Path(args.raw_data_dir).resolve()
    filtered_out_dir = Path(args.filtered_out_dir).resolve()
    blacklist_path = Path(args.blacklist).resolve()

    if not raw_data_dir.exists() or not raw_data_dir.is_dir():
        print(f"Error: raw_data directory not found: {raw_data_dir}")
        return 1

    blacklist = load_blacklist(str(blacklist_path))
    filter_words = list(REPO_NAME_FILTER_WORDS)

    moved_rows: list[dict[str, str]] = []
    reason_counts: Counter[str] = Counter()

    scanned = 0
    excluded = 0
    kept = 0
    undecodable = 0

    for language, repo_dir in iter_repo_dirs(raw_data_dir):
        scanned += 1
        repo_name = decode_repo_from_dir(repo_dir.name)
        if not repo_name:
            undecodable += 1
            continue

        is_excluded, reason = is_repo_excluded(repo_name, blacklist, filter_words)
        if not is_excluded:
            kept += 1
            continue

        excluded += 1
        reason_counts[reason] += 1

        src = repo_dir
        dst = filtered_out_dir / language / repo_dir.name
        dst = ensure_unique_target(dst)

        action = "would_move"
        if args.apply:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            action = "moved"

        moved_rows.append(
            {
                "repo": repo_name,
                "language": language,
                "dir_name": repo_dir.name,
                "reason": reason,
                "src": str(src),
                "dst": str(dst),
                "action": action,
            }
        )

    if args.report_tsv.strip():
        report_path = Path(args.report_tsv).resolve()
    else:
        report_name = "moved_repos.tsv" if args.apply else "dry_run_repos.tsv"
        report_path = filtered_out_dir / report_name

    write_report(report_path, moved_rows)

    print("Raw-data filter summary")
    print(f"  Mode: {'apply' if args.apply else 'dry-run'}")
    print(f"  Raw data dir: {raw_data_dir}")
    print(f"  Filtered out dir: {filtered_out_dir}")
    print(f"  Scanned repo dirs: {scanned}")
    print(f"  Excluded repo dirs: {excluded}")
    print(f"  Kept repo dirs: {kept}")
    print(f"  Undecodable dir names: {undecodable}")
    if reason_counts:
        print("  Exclusion reasons:")
        for reason, count in sorted(reason_counts.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"    - {reason}: {count}")
    print(f"  Report TSV: {report_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
