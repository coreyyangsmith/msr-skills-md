from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import add_instances_input_args, add_output_args, aggregate_instances_to_repo, configure_logging, load_instances_csv, savefig, setup_style

log = logging.getLogger(__name__)


def generate(repo_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    required_columns = {"stars", "skill_count", "total_files_in_skills"}
    if not required_columns.issubset(repo_df.columns):
        log.warning("Missing stars or skill richness columns; skipping Fig 8b.")
        return None

    scatter_df = repo_df[["stars", "skill_count", "total_files_in_skills"]].dropna()
    if len(scatter_df) <= 3:
        log.warning("Not enough rows for Fig 8b.")
        return None

    fig, ax = plt.subplots(figsize=(7, 5))
    scatter = ax.scatter(
        scatter_df["stars"],
        scatter_df["skill_count"],
        c=scatter_df["total_files_in_skills"],
        cmap="YlOrRd",
        s=60,
        alpha=0.7,
        edgecolors="white",
    )
    plt.colorbar(scatter, ax=ax, label="Total files in skills")
    ax.set_xlabel("Repository stars")
    ax.set_ylabel("Number of SKILL.md files")
    ax.set_title("Repository Popularity vs. SKILL.md Count")
    ax.set_xscale("symlog")

    output_path = Path(out_dir) / f"fig8b_stars_vs_skill_count.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 8b for RQ1")
    add_instances_input_args(parser)
    add_output_args(parser)
    args = parser.parse_args(argv)

    configure_logging(args.log_level)
    setup_style()
    inst_df = load_instances_csv(args.instances_csv)
    if inst_df is None:
        return 0
    repo_df = aggregate_instances_to_repo(inst_df)
    generate(repo_df, args.out_dir, args.fig_format, args.dpi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
