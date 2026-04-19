#!/usr/bin/env python3
"""Merge outputs/skill_md_scan_results_errors_retry.csv into skill_only_new_acfs outputs."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

# Mirrors extract_skill_repos.result_category primary error set.
_ERROR_TYPES = frozenset(
    {"rate_limited", "network", "auth", "invalid_repo", "not_found", "other"}
)

REPO_ROOT = Path(__file__).resolve().parents[1]
RETRY_CSV = REPO_ROOT / "outputs" / "skill_md_scan_results_errors_retry.csv"
FULL_CSV = REPO_ROOT / "outputs" / "skill_md_scan_results_skill_only_new_acfs.csv"
FILTERED_PATHS = [
    REPO_ROOT / "data" / "skill_only_scan" / "skill_md_scan_results_skill_only_new_acfs_filtered.csv",
    REPO_ROOT / "outputs" / "skill_md_scan_results_skill_only_new_acfs_filtered.csv",
]
SPLIT_BASE = REPO_ROOT / "outputs" / "skill_md_scan_results_skill_only_new_acfs"


def _row_category(row: dict[str, str]) -> str:
    et = (row.get("error_type") or "").strip().lower()
    found = (row.get("found") or "").strip().lower() == "true"
    if et in _ERROR_TYPES:
        return "errors"
    if found:
        return "found"
    if et == "filtered":
        return "filtered"
    return "not_found"


def _belongs_in_filtered(row: dict[str, str]) -> bool:
    return (row.get("found") or "").strip().lower() == "true" and (
        (row.get("error_type") or "").strip().lower() in ("", "none")
    )


def _align(row: dict[str, str], fieldnames: list[str]) -> dict[str, str]:
    return {k: row.get(k, "") for k in fieldnames}


def _load_retry(path: Path) -> tuple[dict[str, dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise SystemExit(f"No header in {path}")
        fieldnames = list(reader.fieldnames)
        by_repo: dict[str, dict[str, str]] = {}
        order: list[str] = []
        for row in reader:
            repo = (row.get("repo") or "").strip()
            if not repo:
                continue
            by_repo[repo] = dict(row)
            order.append(repo)
    return by_repo, order


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def merge_full(retry_by_repo: dict[str, dict[str, str]], retry_order: list[str]) -> None:
    with FULL_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        full_rows = list(reader)

    seen_in_full = {r["repo"].strip() for r in full_rows}
    out: list[dict[str, str]] = []
    for r in full_rows:
        repo = r["repo"].strip()
        if repo in retry_by_repo:
            out.append(_align(retry_by_repo[repo], fieldnames))
        else:
            out.append(r)

    extra_added: set[str] = set()
    for repo in retry_order:
        if repo in seen_in_full or repo in extra_added:
            continue
        out.append(_align(retry_by_repo[repo], fieldnames))
        extra_added.add(repo)

    _write_csv(FULL_CSV, fieldnames, out)


def merge_filtered(retry_by_repo: dict[str, dict[str, str]], retry_order: list[str]) -> None:
    for path in FILTERED_PATHS:
        if not path.exists():
            print(f"skip missing {path}", file=sys.stderr)
            continue
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)

        remaining = [r for r in rows if r["repo"].strip() not in retry_by_repo]
        seen_add: set[str] = set()
        additions: list[dict[str, str]] = []
        for repo in retry_order:
            if repo in seen_add:
                continue
            seen_add.add(repo)
            if _belongs_in_filtered(retry_by_repo[repo]):
                additions.append(_align(retry_by_repo[repo], fieldnames))
        _write_csv(path, fieldnames, remaining + additions)


def rewrite_splits() -> None:
    with FULL_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        all_rows = list(reader)

    found: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    not_found: list[dict[str, str]] = []

    for r in all_rows:
        cat = _row_category(r)
        if cat == "found":
            found.append(r)
        elif cat == "errors":
            errors.append(r)
        else:
            # not_found and any other non-primary-success category
            not_found.append(r)

    _write_csv(Path(f"{SPLIT_BASE}_found.csv"), fieldnames, found)
    _write_csv(Path(f"{SPLIT_BASE}_errors.csv"), fieldnames, errors)
    _write_csv(Path(f"{SPLIT_BASE}_not_found.csv"), fieldnames, not_found)


def main() -> int:
    if not RETRY_CSV.exists():
        print(f"Missing {RETRY_CSV}", file=sys.stderr)
        return 1
    retry_by_repo, retry_order = _load_retry(RETRY_CSV)
    print(f"Loaded {len(retry_by_repo)} retry rows from {RETRY_CSV.name}")

    merge_full(retry_by_repo, retry_order)
    print(f"Updated {FULL_CSV.relative_to(REPO_ROOT)}")

    merge_filtered(retry_by_repo, retry_order)
    for p in FILTERED_PATHS:
        if p.exists():
            print(f"Updated {p.relative_to(REPO_ROOT)}")

    rewrite_splits()
    print(
        f"Rewrote {SPLIT_BASE.name}_found.csv, "
        f"{SPLIT_BASE.name}_errors.csv, "
        f"{SPLIT_BASE.name}_not_found.csv from merged full"
    )

    with FULL_CSV.open(newline="", encoding="utf-8") as f:
        n = sum(1 for _ in csv.DictReader(f))
    print(f"Full CSV now has {n} data rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
