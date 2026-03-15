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


def generate(repo_df: pd.DataFrame, out_dir: str) -> Path:
    sorted_df = repo_df.sort_values("skill_count", ascending=False).head(1000).copy()
    sorted_df.insert(0, "rank", range(1, len(sorted_df) + 1))
    columns = ["rank", "repo", "skill_count", "mainLanguage", "stars", "forks", "commits", "contributors"]
    columns = [column for column in columns if column in sorted_df.columns]
    output_path = Path(out_dir) / "table_top1000_repos_global.csv"
    write_dataframe(sorted_df[columns], str(output_path))
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the global top-1000 skill repo table for RQ1")
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
