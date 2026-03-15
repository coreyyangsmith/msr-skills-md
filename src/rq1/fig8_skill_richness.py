from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import (
    PALETTE_FOUND,
    add_instances_input_args,
    add_output_args,
    aggregate_instances_to_repo,
    configure_logging,
    load_instances_csv,
    savefig,
    setup_style,
    write_dataframe,
)

log = logging.getLogger(__name__)


def generate(repo_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    metric_columns = [
        ("skill_count", "Skills per Repo"),
        ("total_files_in_skills", "Total Files per Repo"),
        ("references_file_count", "Reference Files"),
        ("assets_file_count", "Asset Files"),
        ("scripts_file_count", "Script Files"),
        ("other_file_count", "Other Files"),
    ]
    available = [(column, label) for column, label in metric_columns if column in repo_df.columns and repo_df[column].notna().any()]
    if not available:
        log.warning("No richness metrics available; skipping Section 8.")
        return None

    rows = []
    for column, label in available:
        series = pd.to_numeric(repo_df[column], errors="coerce").dropna()
        rows.append(
            {
                "metric": label,
                "n": len(series),
                "mean": round(series.mean(), 2),
                "median": round(series.median(), 2),
                "std": round(series.std(), 2),
                "q25": round(series.quantile(0.25), 2),
                "q75": round(series.quantile(0.75), 2),
                "min": int(series.min()),
                "max": int(series.max()),
            }
        )
    write_dataframe(pd.DataFrame(rows), str(Path(out_dir) / "table7_skill_richness_stats.csv"))

    plot_columns = [column for column, _ in available]
    plot_labels = [label for _, label in available]
    fig, axes = plt.subplots(1, len(plot_columns), figsize=(max(10, len(plot_columns) * 2.5), 5))
    if len(plot_columns) == 1:
        axes = [axes]

    for ax, column, label in zip(axes, plot_columns, plot_labels):
        data = pd.to_numeric(repo_df[column], errors="coerce").dropna()
        box = ax.boxplot(data, patch_artist=True, medianprops={"color": "black", "linewidth": 1.5})
        for patch in box["boxes"]:
            patch.set_facecolor(PALETTE_FOUND)
            patch.set_alpha(0.7)
        ax.set_title(label, fontsize=10)
        ax.set_xticks([])
        median = data.median()
        ax.text(1.05, median, f"med={median:.0f}", va="center", fontsize=8, transform=ax.get_yaxis_transform())

    fig.suptitle("Skill File Richness Distribution (SKILL.md Repositories)", y=1.02)
    output_path = Path(out_dir) / f"fig8_skill_richness.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 8 and Table 7 for RQ1")
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
