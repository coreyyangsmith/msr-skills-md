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
    rows = []
    if "mainLanguage" not in repo_df.columns:
        repo_df = repo_df.copy()
        repo_df["mainLanguage"] = "Unknown"

    for language, group_df in repo_df.groupby("mainLanguage"):
        top = group_df.nlargest(100, "skill_count")
        for rank, (_, row) in enumerate(top.iterrows(), start=1):
            rows.append(
                {
                    "language": language,
                    "rank": rank,
                    "repo": row["repo"],
                    "skill_count": row["skill_count"],
                    "stars": row.get("stars"),
                    "forks": row.get("forks"),
                    "commits": row.get("commits"),
                    "contributors": row.get("contributors"),
                }
            )

    output_path = Path(out_dir) / "table_top100_repos_per_language.csv"
    write_dataframe(pd.DataFrame(rows), str(output_path))
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the per-language top-100 skill repo table for RQ1")
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
