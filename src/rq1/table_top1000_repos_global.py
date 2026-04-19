from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import add_instances_input_args, add_output_args, aggregate_instances_to_repo, configure_logging, load_instances_csv, write_dataframe

log = logging.getLogger(__name__)

# Metric columns to rank repos by, with human-readable labels used in the output filename.
RANK_METRICS: list[tuple[str, str]] = [
    ("skill_count", "skill_files"),
    ("total_files_in_skills", "total_files"),
    ("references_file_count", "reference_files"),
    ("assets_file_count", "asset_files"),
    ("scripts_file_count", "script_files"),
    ("other_file_count", "other_files"),
]

# Columns to carry through in every ranked table.
META_COLUMNS = ["repo", "mainLanguage", "stars", "forks", "commits", "contributors"]


def _ranked_table(
    repo_df: pd.DataFrame,
    sort_col: str,
    n: int = 1000,
    ascending: bool = False,
) -> pd.DataFrame:
    if sort_col not in repo_df.columns or not repo_df[sort_col].notna().any():
        return pd.DataFrame()
    cols = [sort_col] + [c for c in META_COLUMNS if c in repo_df.columns and c != sort_col]
    sorted_df = (
        repo_df[cols]
        .dropna(subset=[sort_col])
        .sort_values([sort_col, "repo"], ascending=[ascending, True])
        .head(n)
        .copy()
        .reset_index(drop=True)
    )
    sorted_df.insert(0, "rank", range(1, len(sorted_df) + 1))
    return sorted_df


def generate(repo_df: pd.DataFrame, out_dir: str) -> list[Path]:
    written: list[Path] = []
    for sort_col, label in RANK_METRICS:
        table = _ranked_table(repo_df, sort_col)
        if table.empty:
            log.info("Skipping top-repos table for %s (column absent or all-null).", sort_col)
            continue
        output_path = Path(out_dir) / f"table_top_repos_by_{label}.csv"
        write_dataframe(table, str(output_path))
        written.append(output_path)

        # Also write the inverse ranking for skill-count to surface repositories
        # with the fewest SKILL.md files.
        if sort_col == "skill_count":
            fewest_table = _ranked_table(repo_df, sort_col, ascending=True)
            if not fewest_table.empty:
                fewest_output_path = Path(out_dir) / "table_bottom_repos_by_skill_files.csv"
                write_dataframe(fewest_table, str(fewest_output_path))
                written.append(fewest_output_path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate per-metric top-repo ranked tables for RQ1"
    )
    add_instances_input_args(parser)
    add_output_args(parser)
    args = parser.parse_args(argv)

    configure_logging(args.log_level)
    inst_df = load_instances_csv(args.instances_csv)
    if inst_df is None:
        return 0
    repo_df = aggregate_instances_to_repo(inst_df)
    generate(repo_df, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
