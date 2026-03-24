#!/usr/bin/env python3
"""Wrapper entrypoint for split RQ1 skill-file distribution outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1 import fig11_skill_files_per_repo, table_top1000_repos_global, table_top100_repos_per_language
from rq1.common import (
    add_instances_input_args,
    add_output_args,
    add_scan_input_args,
    aggregate_instances_to_repo,
    configure_logging,
    load_instances_csv,
    load_scan_csv,
    merge_repo_metadata,
    resolve_filters,
    setup_style,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Distribution of skill files per repository")
    add_instances_input_args(parser)
    parser.add_argument("--scan-csv", default="", help="Optional scan CSV to merge repo metadata such as contributors")
    add_output_args(parser)
    parser.add_argument(
        "--blacklist",
        default="blacklist.txt",
        help="Path to blacklist file (owner/repo per line). Default: blacklist.txt",
    )
    parser.add_argument(
        "--name-filter-words",
        default="",
        help="Comma-separated extra repo-name filter words.",
    )
    parser.add_argument(
        "--no-name-filter",
        action="store_true",
        help="Disable the built-in repo-name filter (blacklist still applies).",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    setup_style()

    blacklist, filter_words = resolve_filters(args)
    inst_df = load_instances_csv(args.instances_csv)
    if inst_df is None:
        return 0

    repo_df = aggregate_instances_to_repo(inst_df)
    if args.scan_csv:
        scan_df = load_scan_csv(args.scan_csv, blacklist=blacklist, filter_words=filter_words)
        repo_df = merge_repo_metadata(repo_df, scan_df)

    skill_counts = repo_df["skill_count"]
    print("\n--- Skill files per repository ---")
    print(f"  Min:    {skill_counts.min()}")
    print(f"  Max:    {skill_counts.max()}")
    print(f"  Median: {skill_counts.median():.1f}")
    print(f"  Mean:   {skill_counts.mean():.1f}")

    fig11_skill_files_per_repo.generate(repo_df, args.out_dir, args.fig_format, args.dpi)
    table_top1000_repos_global.generate(repo_df, args.out_dir)
    table_top100_repos_per_language.generate(repo_df, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
