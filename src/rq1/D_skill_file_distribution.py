#!/usr/bin/env python3
"""
D_skill_file_distribution.py

RQ1: Distribution of skill files per repository.

Reads full_skills_instances.csv to produce:
  - Histogram of skill files per repo (fig11_skill_files_per_repo.png)
  - Top 100 repositories across all languages (table_top100_repos_global.csv)
  - Top 100 repositories per language (table_top100_repos_per_language.csv)

Usage:
    uv run python src/rq1/D_skill_file_distribution.py \
        --instances-csv outputs/full_skills_instances.csv \
        --out-dir outputs/rq1

uv run python src/rq1/D_skill_file_distribution.py --instances-csv outputs/full_skills_instances.csv --out-dir outputs/rq1        
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def setup_style() -> None:
    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("seaborn-whitegrid")
    plt.rcParams.update({
        "figure.dpi": 150,
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.constrained_layout.use": True,
    })


def savefig(fig: plt.Figure, path: str, dpi: int = 300) -> None:
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved figure: %s", path)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_instances_csv(path: str) -> pd.DataFrame:
    if not path or not os.path.exists(path):
        log.error("Instances CSV not found: %s", path)
        sys.exit(1)
    df = pd.read_csv(path, low_memory=False)
    log.info("Loaded instances CSV: %s rows from %s", len(df), path)

    # Numeric coercions
    for col in ["stars", "stargazers", "forks", "commits", "contributors"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Fill missing mainLanguage
    if "mainLanguage" in df.columns:
        df["mainLanguage"] = df["mainLanguage"].fillna("Unknown").astype(str).replace("", "Unknown")
    else:
        df["mainLanguage"] = "Unknown"

    return df


def aggregate_by_repo(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate instances to one row per repo with skill_count and metadata."""
    skill_count = df.groupby("repo").size().reset_index(name="skill_count")

    agg_cols = {}
    for col in ["mainLanguage", "stars", "forks", "commits", "contributors"]:
        if col in df.columns:
            # Take first non-null per repo for categorical, max for numeric
            if col == "mainLanguage":
                agg_cols[col] = df.groupby("repo")[col].first()
            else:
                agg_cols[col] = df.groupby("repo")[col].max()

    meta = pd.DataFrame(agg_cols).reset_index()
    merged = skill_count.merge(meta, on="repo", how="left")
    return merged


# ---------------------------------------------------------------------------
# Main analyses
# ---------------------------------------------------------------------------

def plot_histogram(skill_counts: pd.Series, out_dir: str) -> None:
    """Plot distribution of skill files per repository."""
    setup_style()
    counts = skill_counts.values
    counts = counts[counts > 0]

    fig, ax = plt.subplots(figsize=(8, 5))
    max_val = int(counts.max())
    bins = np.arange(0.5, max_val + 1.5, 1) if max_val <= 50 else np.logspace(0, np.log10(max_val + 1), 30)
    if max_val <= 50:
        hist, edges, _ = ax.hist(counts, bins=bins, color="#2196F3", edgecolor="white", linewidth=0.5)
    else:
        hist, edges, _ = ax.hist(counts, bins=bins, color="#2196F3", edgecolor="white", linewidth=0.5)

    median_val = np.median(counts)
    mean_val = np.mean(counts)
    ax.axvline(median_val, color="#FF5722", linestyle="--", linewidth=2, label=f"Median: {median_val:.1f}")
    ax.axvline(mean_val, color="#4CAF50", linestyle=":", linewidth=2, label=f"Mean: {mean_val:.1f}")

    ax.set_xlabel("Number of skill files per repository")
    ax.set_ylabel("Number of repositories")
    ax.set_title("Distribution of Skill Files per Repository")
    ax.legend()
    ax.set_yscale("log")
    savefig(fig, os.path.join(out_dir, "fig11_skill_files_per_repo.png"))


def write_top1000_global(repo_df: pd.DataFrame, out_dir: str) -> None:
    """Write top 1000 repos across all languages."""
    sorted_df = repo_df.sort_values("skill_count", ascending=False).head(1000).copy()
    sorted_df.insert(0, "rank", range(1, len(sorted_df) + 1))
    out_cols = ["rank", "repo", "skill_count", "mainLanguage", "stars", "forks", "commits", "contributors"]
    out_cols = [c for c in out_cols if c in sorted_df.columns]
    sorted_df[out_cols].to_csv(os.path.join(out_dir, "table_top1000_repos_global.csv"), index=False)
    log.info("Saved table_top1000_repos_global.csv")


def write_top100_per_language(repo_df: pd.DataFrame, out_dir: str) -> None:
    """Write top 100 repos per language."""
    rows = []
    for lang, grp in repo_df.groupby("mainLanguage"):
        top = grp.nlargest(100, "skill_count")
        for i, (_, row) in enumerate(top.iterrows(), start=1):
            rows.append({
                "language": lang,
                "rank": i,
                "repo": row["repo"],
                "skill_count": row["skill_count"],
                "stars": row.get("stars"),
                "forks": row.get("forks"),
                "commits": row.get("commits"),
                "contributors": row.get("contributors"),
            })
    out_df = pd.DataFrame(rows)
    out_df.to_csv(os.path.join(out_dir, "table_top100_repos_per_language.csv"), index=False)
    log.info("Saved table_top100_repos_per_language.csv")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Distribution of skill files per repository")
    parser.add_argument(
        "--instances-csv",
        default="outputs/full_skills_instances.csv",
        help="Path to full_skills_instances.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/rq1",
        help="Output directory for figures and tables",
    )
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    df = load_instances_csv(args.instances_csv)
    repo_df = aggregate_by_repo(df)
    skill_counts = repo_df["skill_count"]

    # Summary stats
    print("\n--- Skill files per repository ---")
    print(f"  Min:    {skill_counts.min()}")
    print(f"  Max:    {skill_counts.max()}")
    print(f"  Median: {skill_counts.median():.1f}")
    print(f"  Mean:   {skill_counts.mean():.1f}")

    plot_histogram(skill_counts, args.out_dir)
    write_top1000_global(repo_df, args.out_dir)
    write_top100_per_language(repo_df, args.out_dir)


if __name__ == "__main__":
    main()
