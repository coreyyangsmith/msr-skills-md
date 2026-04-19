#!/usr/bin/env python3
"""Seed and verify SKILL.md instance rows for the current filtered ACF frame.

This utility reuses the existing one-row-per-SKILL.md dataset and writes a
frame-specific output CSV containing only rows whose repositories are present
in the current ACF-filtered source. It also writes a found-style CSV containing
only ACF-frame repositories that are not covered by the existing instance CSV;
that CSV can be passed to ``src/generate_dataset.py`` to retry just the gaps.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _load_plain_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _matched_relevance_term(repo: str, terms: list[str]) -> str:
    name_part = repo.split("/", 1)[-1].lower()
    for term in terms:
        if term.lower() in name_part:
            return term
    return ""


def _is_found(row: dict[str, str]) -> bool:
    return str(row.get("found", "")).strip().lower() in {"true", "1", "yes"}


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _current_instance_fieldnames(instance_fields: list[str]) -> list[str]:
    """Return the current generate_dataset.py schema for instance outputs.

    Older ``full_skills_instances.csv`` files predate the extended ACF columns.
    ``generate_dataset.py --resume`` validates the output header exactly, so the
    seeded output must include those columns before retry rows are appended.
    """
    fields = list(instance_fields)
    extended = ["has_CURSORRULES_MD", "has_INSTRUCTIONS_MD", "has_GEMINI"]
    if "has_COPILOT" not in fields:
        for column in extended:
            if column not in fields:
                fields.append(column)
        return fields

    for column in extended:
        if column in fields:
            fields.remove(column)
    insert_at = fields.index("has_COPILOT") + 1
    fields[insert_at:insert_at] = extended
    return fields


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Reuse existing SKILL.md instance rows for the current ACF-filtered "
            "repository frame and write a retry CSV for uncovered repositories."
        )
    )
    parser.add_argument(
        "--acf-csv",
        default="outputs/skill_md_scan_results_skill_only_new_acfs_filtered.csv",
        help="Current filtered ACF source CSV with one row per SKILL.md repository.",
    )
    parser.add_argument(
        "--instances-csv",
        default="outputs/full_skills_instances.csv",
        help="Existing one-row-per-SKILL.md file to reuse.",
    )
    parser.add_argument(
        "--out-csv",
        default="outputs/full_skills_instances_skill_only_new_acfs_filtered.csv",
        help="Seeded frame-specific SKILL.md instance output CSV.",
    )
    parser.add_argument(
        "--missing-found-csv",
        default="outputs/skill_md_scan_results_skill_only_new_acfs_filtered_missing_instances.csv",
        help="Found-style CSV containing only ACF-frame repos missing from --instances-csv.",
    )
    parser.add_argument(
        "--excluded-report",
        default="outputs/skill_md_scan_results_skill_only_new_acfs_filtered_excluded_by_filters.csv",
        help="Report of ACF source rows excluded by blacklist/relevance terms/found=False.",
    )
    parser.add_argument("--blacklist", default="blacklist.txt")
    parser.add_argument("--relevance-terms", default="relevance_terms.txt")
    parser.add_argument(
        "--summary",
        default="outputs/full_skills_instances_skill_only_new_acfs_filtered_summary.txt",
        help="Plain-text summary path.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    acf_path = Path(args.acf_csv)
    instances_path = Path(args.instances_csv)
    out_path = Path(args.out_csv)
    missing_path = Path(args.missing_found_csv)
    excluded_path = Path(args.excluded_report)
    summary_path = Path(args.summary)

    terms = _load_plain_list(Path(args.relevance_terms))
    blacklist = set(_load_plain_list(Path(args.blacklist)))

    acf_fields, acf_rows = _read_csv(acf_path)
    instance_fields, instance_rows = _read_csv(instances_path)

    included_acf_rows: list[dict[str, str]] = []
    acf_by_repo: dict[str, dict[str, str]] = {}
    excluded_rows: list[dict[str, str]] = []
    excluded_fields = list(acf_fields)
    if "exclusion_reason" not in excluded_fields:
        excluded_fields.append("exclusion_reason")

    seen_repos: set[str] = set()
    duplicate_repos = 0
    for row in acf_rows:
        repo = (row.get("repo") or row.get("name") or "").strip()
        if not repo:
            skipped = dict(row)
            skipped["exclusion_reason"] = "missing_repo"
            excluded_rows.append(skipped)
            continue
        if repo in seen_repos:
            duplicate_repos += 1
            skipped = dict(row)
            skipped["exclusion_reason"] = "duplicate_repo"
            excluded_rows.append(skipped)
            continue
        seen_repos.add(repo)
        if not _is_found(row):
            skipped = dict(row)
            skipped["exclusion_reason"] = "found_false"
            excluded_rows.append(skipped)
            continue
        if repo in blacklist:
            skipped = dict(row)
            skipped["exclusion_reason"] = "blacklist"
            excluded_rows.append(skipped)
            continue
        matched = _matched_relevance_term(repo, terms)
        if matched:
            skipped = dict(row)
            skipped["exclusion_reason"] = f"name_filter:{matched}"
            excluded_rows.append(skipped)
            continue
        included_acf_rows.append(row)
        acf_by_repo[repo] = row

    frame_repos = {
        (row.get("repo") or row.get("name") or "").strip()
        for row in included_acf_rows
    }

    output_fields = _current_instance_fieldnames(instance_fields)
    seeded_rows = []
    for row in instance_rows:
        repo = (row.get("repo") or "").strip()
        if repo not in frame_repos:
            continue
        acf_row = acf_by_repo.get(repo, {})
        out_row = {field: row.get(field, "") for field in output_fields}
        for column in ["has_CURSORRULES_MD", "has_INSTRUCTIONS_MD", "has_GEMINI"]:
            out_row[column] = row.get(column, "") or acf_row.get(column, "") or "0"
        seeded_rows.append(out_row)
    covered_repos = {
        (row.get("repo") or "").strip()
        for row in seeded_rows
        if (row.get("repo") or "").strip()
    }
    missing_repos = frame_repos - covered_repos
    missing_rows = [
        row for row in included_acf_rows
        if (row.get("repo") or row.get("name") or "").strip() in missing_repos
    ]

    _write_csv(out_path, output_fields, seeded_rows)
    _write_csv(missing_path, acf_fields, missing_rows)
    _write_csv(excluded_path, excluded_fields, excluded_rows)

    summary_lines = [
        f"acf_csv={acf_path}",
        f"instances_csv={instances_path}",
        f"out_csv={out_path}",
        f"missing_found_csv={missing_path}",
        f"acf_rows={len(acf_rows)}",
        f"acf_duplicate_repo_rows={duplicate_repos}",
        f"acf_rows_excluded_by_filters_or_found_false={len(excluded_rows)}",
        f"acf_frame_repos={len(frame_repos)}",
        f"seeded_skill_file_rows={len(seeded_rows)}",
        f"seeded_repos={len(covered_repos)}",
        f"missing_repos={len(missing_repos)}",
    ]
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    for line in summary_lines:
        print(line)
    if missing_repos:
        print("missing_repo_list=" + ",".join(sorted(missing_repos)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
