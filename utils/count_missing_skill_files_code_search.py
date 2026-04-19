#!/usr/bin/env python3
"""Count SKILL.md files for ACF-frame repos missing from the instance dataset.

This is a fallback for repositories where the recursive Git tree endpoint is
truncated. It uses GitHub Code Search to count exact-case ``SKILL.md`` paths for
only repositories that are present in the ACF-filtered frame but absent from the
frame-specific instance CSV.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from github_client import GitHubClient, TokenPool, load_tokens_from_env  # noqa: E402


def _is_found(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def _load_tokens(github_tokens: str, github_token: str) -> list[str]:
    raw = (github_tokens or "").strip() or (github_token or "").strip()
    if raw:
        return [token.strip() for token in raw.split(",") if token.strip()]
    return load_tokens_from_env()


def _code_search_skill_paths(
    gh: GitHubClient,
    repo: str,
    filename: str,
    max_pages: int,
) -> tuple[list[str], int, str]:
    paths: list[str] = []
    total_count = 0
    incomplete = ""
    for page in range(1, max_pages + 1):
        query = f"repo:{repo} filename:{filename}"
        status, data, err = gh.request_json(
            "GET",
            "/search/code",
            params={"q": query, "per_page": 100, "page": page},
            is_search=True,
        )
        if status != 200 or not isinstance(data, dict):
            return paths, total_count, err or f"http_{status}"
        if page == 1:
            total_count = int(data.get("total_count") or 0)
            incomplete = "true" if data.get("incomplete_results") else "false"
        items = data.get("items") or []
        for item in items:
            path = item.get("path") or ""
            if os.path.basename(path) == filename:
                paths.append(path)
        if len(items) < 100:
            break
    return sorted(set(paths)), total_count, f"incomplete_results={incomplete}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Count missing SKILL.md files with GitHub Code Search.")
    parser.add_argument("--acf-csv", default="outputs/skill_md_scan_results_skill_only_new_acfs_filtered.csv")
    parser.add_argument("--instances-csv", default="outputs/full_skills_instances_skill_only_new_acfs_filtered.csv")
    parser.add_argument("--out-csv", default="outputs/missing_skill_file_counts_code_search.csv")
    parser.add_argument("--summary", default="outputs/full_skills_instances_skill_only_new_acfs_filtered_count_summary.txt")
    parser.add_argument("--match-name", default="SKILL.md")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--github-token", default="")
    parser.add_argument("--github-tokens", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    acf_fields, acf_rows = _read_csv(Path(args.acf_csv))
    _instance_fields, instance_rows = _read_csv(Path(args.instances_csv))
    del acf_fields

    acf_repos = {
        (row.get("repo") or row.get("name") or "").strip()
        for row in acf_rows
        if _is_found(row.get("found", ""))
    }
    covered_repos = {
        (row.get("repo") or "").strip()
        for row in instance_rows
        if (row.get("repo") or "").strip()
    }
    missing_repos = sorted(acf_repos - covered_repos)

    tokens = _load_tokens(args.github_tokens, args.github_token)
    gh = GitHubClient(TokenPool(tokens))

    output_rows: list[dict[str, str]] = []
    for repo in missing_repos:
        paths, api_total_count, status = _code_search_skill_paths(
            gh,
            repo,
            args.match_name,
            args.max_pages,
        )
        output_rows.append(
            {
                "repo": repo,
                "exact_skill_path_count": str(len(paths)),
                "api_total_count": str(api_total_count),
                "status": status,
                "skill_paths": ";".join(paths),
            }
        )

    out_path = Path(args.out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["repo", "exact_skill_path_count", "api_total_count", "status", "skill_paths"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    instance_count = len(instance_rows)
    supplemental_count = sum(int(row["exact_skill_path_count"]) for row in output_rows)
    summary_lines = [
        f"acf_repos={len(acf_repos)}",
        f"instance_skill_file_rows={instance_count}",
        f"instance_covered_repos={len(covered_repos)}",
        f"missing_repos={len(missing_repos)}",
        f"supplemental_code_search_skill_files={supplemental_count}",
        f"updated_skill_file_count={instance_count + supplemental_count}",
        f"supplemental_counts_csv={out_path}",
    ]
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    for line in summary_lines:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
