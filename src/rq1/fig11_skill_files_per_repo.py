from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import add_instances_input_args, add_output_args, aggregate_instances_to_repo, configure_logging, load_instances_csv, savefig, setup_style

log = logging.getLogger(__name__)


def generate(repo_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    if "skill_count" not in repo_df.columns:
        log.warning("skill_count is missing; skipping skill-file histogram.")
        return None

    skill_counts = pd.to_numeric(repo_df["skill_count"], errors="coerce").dropna()
    skill_counts = skill_counts[skill_counts > 0]
    if skill_counts.empty:
        log.warning("No positive skill counts available.")
        return None

    fig, ax = plt.subplots(figsize=(8, 5))
    max_value = int(skill_counts.max())
    bins = np.arange(0.5, max_value + 1.5, 1) if max_value <= 50 else np.logspace(0, np.log10(max_value + 1), 30)
    ax.hist(skill_counts, bins=bins, color="#2196F3", edgecolor="white", linewidth=0.5)

    median = np.median(skill_counts)
    mean = np.mean(skill_counts)
    ax.axvline(median, color="#FF5722", linestyle="--", linewidth=2, label=f"Median: {median:.1f}")
    ax.axvline(mean, color="#4CAF50", linestyle=":", linewidth=2, label=f"Mean: {mean:.1f}")
    ax.set_xlabel("Number of skill files per repository")
    ax.set_ylabel("Number of repositories")
    ax.set_title("Distribution of Skill Files per Repository")
    ax.legend()
    ax.set_yscale("log")

    output_path = Path(out_dir) / f"fig11_skill_files_per_repo.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the skill-file distribution figure for RQ1")
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
