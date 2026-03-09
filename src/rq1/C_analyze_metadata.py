#!/usr/bin/env python3
"""
C_analyze_metadata.py

RQ1: Prevalence and adoption analysis of SKILL.md across open-source repositories.

Reads the scan results CSV (from B_extract_skill_repos.py) and optionally the
full_skills_instances CSV (from C_generate_dataset.py) to produce:
  - Summary statistics tables (CSV)
  - Publication-quality figures (PNG/PDF/SVG)

All outputs are written to --out-dir (default: outputs/rq1/).

Usage:
    uv run python src/rq1/C_analyze_metadata.py \
        --scan-csv outputs/skill_md_scan_results.csv \
        --instances-csv outputs/ss/full_skills_instances.csv \
        --out-dir outputs/rq1

uv run python src/rq1/C_analyze_metadata.py --scan-csv outputs/skill_md_scan_results.csv --instances-csv outputs/ss/full_skills_instances.csv --out-dir outputs/rq1     
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
import warnings
from typing import List, Optional, Set

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for server/CI use
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns

warnings.filterwarnings("ignore", category=FutureWarning)

# Add src/ to path so we can import sibling modules when invoked from any cwd.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from filters import (  # noqa: E402
    REPO_NAME_FILTER_WORDS,
    load_blacklist,
    repo_name_contains_filter_word,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

PALETTE_FOUND = "#2196F3"      # blue  – SKILL.md found
PALETTE_NOT_FOUND = "#E0E0E0"  # grey  – not found
PALETTE_ACF = ["#FF5722", "#4CAF50", "#9C27B0"]  # CLAUDE, AGENTS, COPILOT

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

def _apply_repo_filters(
    df: pd.DataFrame,
    blacklist: Set[str],
    filter_words: List[str],
    label: str,
) -> pd.DataFrame:
    """Drop rows whose 'repo' column matches the blacklist or name-filter words."""
    if "repo" not in df.columns:
        return df
    before = len(df)
    mask_blacklist = df["repo"].isin(blacklist)
    mask_name = df["repo"].apply(
        lambda r: repo_name_contains_filter_word(str(r), filter_words) is not None
    )
    excluded = mask_blacklist | mask_name
    n_bl = int(mask_blacklist.sum())
    n_nf = int((~mask_blacklist & mask_name).sum())
    if n_bl or n_nf:
        log.info(
            "%s: excluding %d blacklisted + %d name-filtered repos (%d → %d rows)",
            label, n_bl, n_nf, before, before - int(excluded.sum()),
        )
    return df[~excluded].reset_index(drop=True)


def load_scan_csv(
    path: str,
    blacklist: Optional[Set[str]] = None,
    filter_words: Optional[List[str]] = None,
) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    log.info("Loaded scan CSV: %s rows, %s cols from %s", len(df), len(df.columns), path)

    # Apply blacklist and name filter
    df = _apply_repo_filters(
        df,
        blacklist or set(),
        filter_words if filter_words is not None else REPO_NAME_FILTER_WORDS,
        "scan CSV",
    )

    # Normalise the 'found' column to bool
    if "found" in df.columns:
        df["found"] = df["found"].astype(str).str.strip().str.lower().map(
            {"true": True, "false": False, "1": True, "0": False}
        ).fillna(False).astype(bool)

    # Numeric coercions
    for col in ["stars", "stargazers", "codeLines", "size", "commits",
                "contributors", "forks", "releases"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Datetime coercions
    for col in ["createdAt", "pushedAt", "updatedAt", "lastCommit"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    return df


def load_instances_csv(
    path: str,
    blacklist: Optional[Set[str]] = None,
    filter_words: Optional[List[str]] = None,
) -> Optional[pd.DataFrame]:
    if not path or not os.path.exists(path):
        log.warning("Instances CSV not found or not provided: %s", path)
        return None
    df = pd.read_csv(path, low_memory=False)
    log.info("Loaded instances CSV: %s rows from %s", len(df), path)

    # Apply blacklist and name filter
    df = _apply_repo_filters(
        df,
        blacklist or set(),
        filter_words if filter_words is not None else REPO_NAME_FILTER_WORDS,
        "instances CSV",
    )

    for col in ["skill_count", "total_files_in_skills", "references_file_count",
                "assets_file_count", "scripts_file_count", "other_file_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    if "stars" in df.columns:
        df["stars"] = pd.to_numeric(df["stars"], errors="coerce")
    return df


def merge_instances(scan_df: pd.DataFrame, inst_df: pd.DataFrame) -> pd.DataFrame:
    """Left-join skill instance metrics onto the found subset of scan_df."""
    found = scan_df[scan_df["found"]].copy()
    cols = [c for c in inst_df.columns if c != "repo"]
    merged = found.merge(inst_df[["repo"] + cols], on="repo", how="left")
    return merged


def _safe_stars(df: pd.DataFrame) -> pd.Series:
    """Return a numeric stars series, preferring 'stargazers' over 'stars'."""
    if "stargazers" in df.columns and df["stargazers"].notna().any():
        return df["stargazers"]
    return df.get("stars", pd.Series(dtype=float))


# ---------------------------------------------------------------------------
# Section 1: Dataset overview
# ---------------------------------------------------------------------------

def analyze_overview(df: pd.DataFrame, out_dir: str) -> pd.DataFrame:
    log.info("=== Section 1: Dataset Overview ===")

    total = len(df)
    found_mask = df["found"]
    n_found = found_mask.sum()
    n_not_found = (~found_mask).sum()

    error_cols = df.get("error_type", pd.Series(dtype=str))
    n_errors = int((error_cols.isin(["rate_limited", "network", "auth",
                                     "invalid_repo", "not_found", "other"])).sum())
    n_filtered = int((error_cols == "filtered").sum())

    prevalence = 100.0 * n_found / total if total else 0.0

    rows = [
        ("Total repos scanned", total),
        ("SKILL.md found", n_found),
        ("SKILL.md not found", n_not_found),
        ("API errors", n_errors),
        ("Filtered out", n_filtered),
        ("Prevalence rate (%)", f"{prevalence:.2f}"),
    ]
    summary = pd.DataFrame(rows, columns=["Metric", "Value"])
    out_path = os.path.join(out_dir, "table1_dataset_summary.csv")
    summary.to_csv(out_path, index=False)
    log.info("Table 1 saved: %s", out_path)

    # Print nicely
    print("\n=== Table 1: Dataset Summary ===")
    print(summary.to_string(index=False))

    return summary


# ---------------------------------------------------------------------------
# Section 2: Prevalence by primary language
# ---------------------------------------------------------------------------

def analyze_by_language(df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> None:
    log.info("=== Section 2: Prevalence by Language ===")

    lang_col = "mainLanguage" if "mainLanguage" in df.columns else None
    if lang_col is None:
        log.warning("No mainLanguage column; skipping language analysis.")
        return

    grp = (
        df.groupby(lang_col, dropna=False)["found"]
        .agg(total="count", found_count="sum")
        .reset_index()
        .rename(columns={lang_col: "language"})
    )
    grp["language"] = grp["language"].fillna("(unknown)")
    grp["prevalence_pct"] = 100.0 * grp["found_count"] / grp["total"]

    # Wilson 95% CI
    def wilson_ci(k, n, z=1.96):
        if n == 0:
            return 0.0, 0.0
        p = k / n
        denom = 1 + z**2 / n
        centre = (p + z**2 / (2 * n)) / denom
        half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
        return max(0, 100 * (centre - half)), min(100, 100 * (centre + half))

    grp[["ci_lo", "ci_hi"]] = grp.apply(
        lambda r: pd.Series(wilson_ci(r["found_count"], r["total"])), axis=1
    )
    grp["ci_err_lo"] = grp["prevalence_pct"] - grp["ci_lo"]
    grp["ci_err_hi"] = grp["ci_hi"] - grp["prevalence_pct"]

    # Save full table
    tbl = grp.sort_values("found_count", ascending=False)
    tbl.to_csv(os.path.join(out_dir, "table2_language_breakdown.csv"), index=False)

    # Figure: top languages by found count (at least 1 found)
    plot_df = grp[grp["found_count"] >= 1].sort_values("found_count", ascending=True)

    fig, axes = plt.subplots(1, 2, figsize=(14, max(5, len(plot_df) * 0.45 + 1.5)))

    # Left: absolute found counts
    ax0 = axes[0]
    bars0 = ax0.barh(plot_df["language"], plot_df["found_count"],
                     color=PALETTE_FOUND, edgecolor="white", linewidth=0.5)
    ax0.set_xlabel("Repos with SKILL.md (count)")
    ax0.set_title("Repositories with SKILL.md\nby Primary Language")
    for bar, tot in zip(bars0, plot_df["total"]):
        ax0.text(bar.get_width() + 0.1, bar.get_y() + bar.get_height() / 2,
                 f"/{int(tot)}", va="center", fontsize=8, color="#555")

    # Right: prevalence %
    ax1 = axes[1]
    xerr = [plot_df["ci_err_lo"].values, plot_df["ci_err_hi"].values]
    ax1.barh(plot_df["language"], plot_df["prevalence_pct"],
             xerr=xerr, color=PALETTE_FOUND, edgecolor="white",
             linewidth=0.5, capsize=3, error_kw={"elinewidth": 1, "alpha": 0.7})
    ax1.set_xlabel("Prevalence rate (%)")
    ax1.set_title("SKILL.md Prevalence Rate\nby Primary Language (95% CI)")
    ax1.set_xlim(left=0)

    out_path = os.path.join(out_dir, f"fig1_prevalence_by_language.{fig_format}")
    savefig(fig, out_path, dpi)
    log.info("Figure 1 saved: %s", out_path)


# ---------------------------------------------------------------------------
# Section 3: Prevalence by size and stars
# ---------------------------------------------------------------------------

def analyze_by_size_stars(df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> None:
    log.info("=== Section 3: Prevalence by Size & Stars ===")

    stars_col = _safe_stars(df)
    code_col = df.get("codeLines", pd.Series(dtype=float))

    if stars_col.isna().all() and code_col.isna().all():
        log.warning("No numeric size/stars columns; skipping size analysis.")
        return

    work = df[["found"]].copy()
    work["stars"] = stars_col.values

    # Star tiers
    star_bins = [0, 100, 500, 5000, float("inf")]
    star_labels = ["<100", "100–499", "500–4999", "≥5000"]
    work["star_tier"] = pd.cut(work["stars"], bins=star_bins, labels=star_labels, right=False)

    # Code lines tiers
    if "codeLines" in df.columns:
        work["codeLines"] = df["codeLines"].values
        cl_bins = [0, 1000, 10000, 100000, float("inf")]
        cl_labels = ["Small\n(<1K)", "Medium\n(1K–10K)", "Large\n(10K–100K)", "Very Large\n(>100K)"]
        work["size_tier"] = pd.cut(work["codeLines"], bins=cl_bins, labels=cl_labels, right=False)
    else:
        work["size_tier"] = pd.NA

    # --- Figure A: prevalence by star tier ---
    star_grp = (
        work.groupby("star_tier", observed=True)["found"]
        .agg(total="count", found_count="sum")
        .reset_index()
    )
    star_grp["prevalence_pct"] = 100.0 * star_grp["found_count"] / star_grp["total"].replace(0, np.nan)

    # --- Figure B: heatmap star tier x size tier (if size available) ---
    has_size = work["size_tier"].notna().any()

    if has_size:
        pivot = (
            work.groupby(["size_tier", "star_tier"], observed=True)["found"]
            .agg(total="count", found_count="sum")
            .reset_index()
        )
        pivot["prevalence_pct"] = 100.0 * pivot["found_count"] / pivot["total"].replace(0, np.nan)
        heat_data = pivot.pivot_table(
            index="size_tier", columns="star_tier",
            values="prevalence_pct", observed=True
        )
        count_data = pivot.pivot_table(
            index="size_tier", columns="star_tier",
            values="total", observed=True, aggfunc="sum"
        )

        fig, axes = plt.subplots(1, 2, figsize=(15, 5))

        ax0 = axes[0]
        colors = sns.color_palette("Blues", n_colors=len(star_grp))
        bars = ax0.bar(star_grp["star_tier"].astype(str), star_grp["prevalence_pct"],
                       color=colors, edgecolor="white")
        for bar, row in zip(bars, star_grp.itertuples()):
            ax0.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                     f"{row.found_count}/{row.total}",
                     ha="center", va="bottom", fontsize=9)
        ax0.set_xlabel("Star tier")
        ax0.set_ylabel("Prevalence rate (%)")
        ax0.set_title("SKILL.md Prevalence by Repository Popularity")

        ax1 = axes[1]
        annot = heat_data.round(1).astype(str).where(heat_data.notna(), other="–")
        for r_idx, r_label in enumerate(heat_data.index):
            for c_idx, c_label in enumerate(heat_data.columns):
                n = count_data.loc[r_label, c_label] if r_label in count_data.index and c_label in count_data.columns else np.nan
                if not np.isnan(n):
                    annot.loc[r_label, c_label] = f"{heat_data.loc[r_label, c_label]:.1f}%\nn={int(n)}"

        sns.heatmap(heat_data, annot=annot, fmt="", cmap="YlOrRd",
                    linewidths=0.5, ax=ax1, cbar_kws={"label": "Prevalence %"},
                    annot_kws={"size": 9})
        ax1.set_title("SKILL.md Prevalence (%) by\nProject Size × Popularity")
        ax1.set_xlabel("Star tier")
        ax1.set_ylabel("Code lines tier")

    else:
        fig, ax0 = plt.subplots(figsize=(7, 5))
        colors = sns.color_palette("Blues", n_colors=len(star_grp))
        bars = ax0.bar(star_grp["star_tier"].astype(str), star_grp["prevalence_pct"],
                       color=colors, edgecolor="white")
        for bar, row in zip(bars, star_grp.itertuples()):
            ax0.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                     f"{row.found_count}/{row.total}",
                     ha="center", va="bottom", fontsize=9)
        ax0.set_xlabel("Star tier")
        ax0.set_ylabel("Prevalence rate (%)")
        ax0.set_title("SKILL.md Prevalence by Repository Popularity")

    out_path = os.path.join(out_dir, f"fig2_prevalence_by_size_stars.{fig_format}")
    savefig(fig, out_path, dpi)

    # Save table
    tbl_rows = []
    for tier in star_labels:
        sub = work[work["star_tier"] == tier]["found"]
        n_total = len(sub)
        n_found = sub.sum()
        pct = 100.0 * n_found / n_total if n_total else 0
        tbl_rows.append({"tier_type": "stars", "tier": tier,
                         "total": n_total, "found": n_found, "prevalence_pct": round(pct, 2)})

    if has_size:
        for tier in cl_labels:
            sub = work[work["size_tier"] == tier]["found"]
            n_total = len(sub)
            n_found = sub.sum()
            pct = 100.0 * n_found / n_total if n_total else 0
            tbl_rows.append({"tier_type": "code_lines", "tier": tier.replace("\n", " "),
                             "total": n_total, "found": n_found, "prevalence_pct": round(pct, 2)})

    pd.DataFrame(tbl_rows).to_csv(
        os.path.join(out_dir, "table3_size_star_breakdown.csv"), index=False
    )
    log.info("Section 3 done.")


# ---------------------------------------------------------------------------
# Section 4: ACF co-occurrence
# ---------------------------------------------------------------------------

def analyze_acf_cooccurrence(df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> None:
    log.info("=== Section 4: ACF Co-occurrence ===")

    acf_cols = {
        "has_CLAUDE": "CLAUDE.md",
        "has_AGENTS": "AGENTS.md",
        "has_COPILOT": "copilot-instructions.md",
    }
    present = [c for c in acf_cols if c in df.columns]
    if not present:
        log.warning("ACF columns not present in scan CSV; skipping Section 4.")
        return

    found_df = df[df["found"]].copy()
    if len(found_df) == 0:
        log.warning("No found repos; skipping ACF analysis.")
        return

    # Normalize to 0/1 int
    for col in present:
        found_df[col] = pd.to_numeric(found_df[col], errors="coerce").fillna(0).astype(int)

    # --- Table: co-occurrence counts ---
    rows = []
    for col, label in acf_cols.items():
        if col not in found_df.columns:
            continue
        n = int(found_df[col].sum())
        pct = 100.0 * n / len(found_df)
        rows.append({"artifact": label, "count": n,
                     "pct_of_skill_md_repos": round(pct, 1)})

    # Pairwise co-occurrence
    if len(present) >= 2:
        for i, c1 in enumerate(present):
            for c2 in present[i+1:]:
                n = int((found_df[c1] & found_df[c2]).sum())
                rows.append({
                    "artifact": f"{acf_cols[c1]} + {acf_cols[c2]}",
                    "count": n,
                    "pct_of_skill_md_repos": round(100.0 * n / len(found_df), 1),
                })
    if len(present) == 3:
        n_all = int((found_df[present[0]] & found_df[present[1]] & found_df[present[2]]).sum())
        rows.append({
            "artifact": "All three",
            "count": n_all,
            "pct_of_skill_md_repos": round(100.0 * n_all / len(found_df), 1),
        })

    tbl = pd.DataFrame(rows)
    tbl.to_csv(os.path.join(out_dir, "table4_acf_cooccurrence.csv"), index=False)

    # --- Figure 3: Stacked bar chart of ACF presence ---
    fig3, ax0 = plt.subplots(figsize=(7, 5))

    single_rows = [r for r in rows if "+" not in r["artifact"] and r["artifact"] != "All three"]
    labels = [r["artifact"] for r in single_rows]
    counts = [r["count"] for r in single_rows]
    not_counts = [len(found_df) - c for c in counts]

    x = np.arange(len(labels))
    width = 0.5
    p1 = ax0.bar(x, counts, width, label="Has artifact", color=PALETTE_ACF[:len(labels)],
                 edgecolor="white")
    p2 = ax0.bar(x, not_counts, width, bottom=counts, label="No artifact",  # noqa: F841
                 color=PALETTE_NOT_FOUND, edgecolor="white")
    ax0.set_xticks(x)
    ax0.set_xticklabels(labels, rotation=15, ha="right")
    ax0.set_ylabel("Repository count")
    ax0.set_title("Agent-Facing Artifact Co-occurrence\namong SKILL.md Repositories")
    ax0.legend(loc="upper right")
    for bar, cnt in zip(p1, counts):
        if cnt > 0:
            ax0.text(bar.get_x() + bar.get_width() / 2,
                     bar.get_height() / 2, str(cnt),
                     ha="center", va="center", fontsize=9, color="white", fontweight="bold")

    out_path3 = os.path.join(out_dir, f"fig3_acf_cooccurrence.{fig_format}")
    savefig(fig3, out_path3, dpi)

    # --- Figure 4: Heatmap of pairwise co-occurrence (standalone) ---
    if len(present) >= 2:
        mat_labels = [acf_cols[c] for c in present]
        n_acf = len(present)
        mat = np.zeros((n_acf, n_acf), dtype=float)
        for i, c1 in enumerate(present):
            for j, c2 in enumerate(present):
                mat[i, j] = int((found_df[c1] & found_df[c2]).sum())

        fig4, ax4 = plt.subplots(figsize=(6, 5))
        sns.heatmap(mat, annot=True, fmt=".0f", xticklabels=mat_labels,
                    yticklabels=mat_labels, cmap="YlOrRd", ax=ax4,
                    linewidths=0.5, cbar_kws={"label": "Co-occurring repos"})
        ax4.set_title("Pairwise ACF Co-occurrence\n(SKILL.md repos only)")
        out_path4 = os.path.join(out_dir, f"fig4_acf_pairwise_heatmap.{fig_format}")
        savefig(fig4, out_path4, dpi)
        log.info("Figure 4 saved: %s", out_path4)
    else:
        log.warning("Fewer than 2 ACF columns present; skipping Fig 4 pairwise heatmap.")

    log.info("Section 4 done.")


# ---------------------------------------------------------------------------
# Section 5: SKILL.md placement patterns
# ---------------------------------------------------------------------------

def _classify_placement(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        return "unknown"
    p = path.strip().lower().lstrip("/")
    if p == "skill.md":
        return "root"
    if p.startswith(".github/"):
        return ".github/ subtree"
    if re.match(r"^(skills?|claude-?skill|codex-?skill|skill-?set)/", p):
        return "skills/ subfolder"
    if re.match(r"^\.(cursor|codex|vscode|config)/", p):
        return ".cursor/.codex/config subtree"
    if re.match(r"^nanobot/", p):
        return "nanobot/ subtree"
    return "other subfolder"


def analyze_placement_patterns(df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> None:
    log.info("=== Section 5: Placement Patterns ===")

    found_df = df[df["found"]].copy()
    if len(found_df) == 0 or "match_path" not in found_df.columns:
        log.warning("No found repos or match_path missing; skipping placement analysis.")
        return

    # For repos with multiple skill paths (from full scan), use skill_paths if available
    if "skill_paths" in found_df.columns:
        # Expand multi-skill repos
        all_paths = []
        for _, row in found_df.iterrows():
            paths_raw = str(row.get("skill_paths") or row.get("match_path") or "")
            for p in paths_raw.split(";"):
                p = p.strip()
                if p:
                    all_paths.append(p)
        paths_series = pd.Series(all_paths)
    else:
        paths_series = found_df["match_path"].dropna()

    placement = paths_series.map(_classify_placement)
    counts = placement.value_counts()

    tbl = counts.reset_index()
    tbl.columns = ["placement", "count"]
    tbl["pct"] = (100.0 * tbl["count"] / tbl["count"].sum()).round(1)
    tbl.to_csv(os.path.join(out_dir, "table5_placement_patterns.csv"), index=False)

    # Figure: donut chart
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))

    ax0 = axes[0]
    colors_pie = sns.color_palette("Set2", n_colors=len(counts))
    wedges, texts, autotexts = ax0.pie(
        counts.values,
        labels=None,
        autopct="%1.1f%%",
        pctdistance=0.75,
        colors=colors_pie,
        startangle=90,
        wedgeprops={"width": 0.55, "edgecolor": "white", "linewidth": 1.5},
    )
    for at in autotexts:
        at.set_fontsize(9)
    ax0.legend(wedges, [f"{k} (n={v})" for k, v in zip(counts.index, counts.values)],
               loc="lower center", bbox_to_anchor=(0.5, -0.18),
               ncol=2, fontsize=9)
    ax0.set_title("SKILL.md Placement Location Distribution")

    # Bar chart on right
    ax1 = axes[1]
    ax1.barh(tbl["placement"][::-1], tbl["count"][::-1], color=colors_pie[::-1],
             edgecolor="white")
    for i, (cnt, pct) in enumerate(zip(tbl["count"][::-1], tbl["pct"][::-1])):
        ax1.text(cnt + 0.2, i, f"{cnt} ({pct}%)", va="center", fontsize=9)
    ax1.set_xlabel("Number of SKILL.md instances")
    ax1.set_title("SKILL.md Placement (absolute counts)")
    ax1.set_xlim(right=tbl["count"].max() * 1.35)

    out_path = os.path.join(out_dir, f"fig5_placement_patterns.{fig_format}")
    savefig(fig, out_path, dpi)
    log.info("Section 5 done.")


# ---------------------------------------------------------------------------
# Section 6: Temporal adoption trend
# ---------------------------------------------------------------------------

def analyze_temporal_trend(df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> None:
    log.info("=== Section 6: Temporal Trend ===")

    date_col = None
    for c in ["pushedAt", "createdAt", "lastCommit"]:
        if c in df.columns and df[c].notna().any():
            date_col = c
            break
    if date_col is None:
        log.warning("No datetime column available; skipping temporal analysis.")
        return

    found_df = df[df["found"] & df[date_col].notna()].copy()
    all_df = df[df[date_col].notna()].copy()

    if len(found_df) == 0:
        log.warning("No dated found repos; skipping temporal analysis.")
        return

    found_df["month"] = found_df[date_col].dt.tz_convert(None).dt.to_period("M")
    all_df["month"] = all_df[date_col].dt.tz_convert(None).dt.to_period("M")

    found_counts = found_df.groupby("month").size().rename("found")
    all_counts = all_df.groupby("month").size().rename("total")

    trend = pd.concat([found_counts, all_counts], axis=1).fillna(0)
    trend["prevalence_pct"] = 100.0 * trend["found"] / trend["total"].replace(0, np.nan)

    trend_sorted = trend.sort_index()

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    ax0 = axes[0]
    months = [str(m) for m in trend_sorted.index]
    x = np.arange(len(months))
    ax0.bar(x, trend_sorted["found"], color=PALETTE_FOUND, alpha=0.85, label="With SKILL.md")
    ax0.set_ylabel("Repositories with SKILL.md")
    ax0.set_title(f"SKILL.md Adoption Over Time (by month, {date_col})")
    ax0.legend()

    ax1 = axes[1]
    ax1.plot(x, trend_sorted["total"], color="#9E9E9E", linewidth=1.5, linestyle="--",
             label="Total repos scanned")
    ax1.set_ylabel("Total repos in cohort")
    ax1.set_xticks(x)
    ax1.set_xticklabels(months, rotation=45, ha="right", fontsize=8)
    ax1.legend()

    out_path = os.path.join(out_dir, f"fig6_temporal_trend.{fig_format}")
    savefig(fig, out_path, dpi)

    trend_sorted.reset_index().to_csv(
        os.path.join(out_dir, "table_temporal_trend.csv"), index=False
    )
    log.info("Section 6 done.")


# ---------------------------------------------------------------------------
# Section 7: Topic enrichment
# ---------------------------------------------------------------------------

def analyze_topics(df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> None:
    log.info("=== Section 7: Topic Enrichment ===")

    if "topics" not in df.columns:
        log.warning("No topics column; skipping topic analysis.")
        return

    def parse_topics(val: str):
        if not isinstance(val, str) or not val.strip():
            return []
        return [t.strip() for t in val.split(";") if t.strip()]

    all_topics: list[str] = []
    found_topics: list[str] = []

    for _, row in df.iterrows():
        ts = parse_topics(str(row.get("topics") or ""))
        all_topics.extend(ts)
        if row.get("found"):
            found_topics.extend(ts)

    if not all_topics:
        log.warning("No topic data found; skipping topic analysis.")
        return

    all_counts = pd.Series(all_topics).value_counts()
    found_counts = pd.Series(found_topics).value_counts()

    n_total = len(df)
    n_found_repos = int(df["found"].sum())

    tbl = pd.DataFrame({
        "topic": all_counts.index,
        "total_repos": all_counts.values,
    })
    tbl["found_repos"] = tbl["topic"].map(found_counts).fillna(0).astype(int)
    tbl["found_rate_pct"] = 100.0 * tbl["found_repos"] / tbl["total_repos"].replace(0, np.nan)
    overall_rate = 100.0 * n_found_repos / n_total if n_total else 0
    tbl["enrichment_ratio"] = tbl["found_rate_pct"] / overall_rate if overall_rate else np.nan
    tbl = tbl.sort_values("enrichment_ratio", ascending=False)

    top20 = tbl[tbl["total_repos"] >= 2].head(20)
    top20.to_csv(os.path.join(out_dir, "table6_topic_enrichment.csv"), index=False)

    # Figure: top topics among found repos
    top_found = found_counts.head(20)
    fig, axes = plt.subplots(1, 2, figsize=(14, 7))

    ax0 = axes[0]
    colors0 = sns.color_palette("Blues_r", n_colors=len(top_found))
    ax0.barh(top_found.index[::-1], top_found.values[::-1], color=colors0[::-1], edgecolor="white")
    ax0.set_xlabel("Frequency in SKILL.md repositories")
    ax0.set_title("Top Topics in SKILL.md Repositories")

    ax1 = axes[1]
    plot_enrich = top20[top20["enrichment_ratio"].notna()].head(15)
    colors1 = sns.color_palette("Oranges_r", n_colors=len(plot_enrich))
    ax1.barh(plot_enrich["topic"][::-1], plot_enrich["enrichment_ratio"][::-1],
             color=colors1[::-1], edgecolor="white")
    ax1.axvline(1.0, color="gray", linestyle="--", linewidth=1, label="Baseline rate")
    ax1.set_xlabel("Enrichment ratio (vs. overall prevalence)")
    ax1.set_title("Most Enriched Topics in SKILL.md Repos\n(min. 2 total repos)")
    ax1.legend()

    out_path = os.path.join(out_dir, f"fig7_topic_analysis.{fig_format}")
    savefig(fig, out_path, dpi)
    log.info("Section 7 done.")


# ---------------------------------------------------------------------------
# Section 8: Skill file richness
# ---------------------------------------------------------------------------

def analyze_skill_richness(inst_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> None:
    log.info("=== Section 8: Skill File Richness ===")

    metric_cols = [
        ("skill_count", "Skills per Repo"),
        ("total_files_in_skills", "Total Files per Repo"),
        ("references_file_count", "Reference Files"),
        ("assets_file_count", "Asset Files"),
        ("scripts_file_count", "Script Files"),
        ("other_file_count", "Other Files"),
    ]
    available = [(col, lbl) for col, lbl in metric_cols if col in inst_df.columns]

    if not available:
        log.warning("No richness metrics available; skipping Section 8.")
        return

    # --- Descriptive stats table ---
    stats_rows = []
    for col, lbl in available:
        s = inst_df[col].dropna()
        stats_rows.append({
            "metric": lbl,
            "n": len(s),
            "mean": round(s.mean(), 2),
            "median": round(s.median(), 2),
            "std": round(s.std(), 2),
            "q25": round(s.quantile(0.25), 2),
            "q75": round(s.quantile(0.75), 2),
            "min": int(s.min()),
            "max": int(s.max()),
        })
    stats_tbl = pd.DataFrame(stats_rows)
    stats_tbl.to_csv(os.path.join(out_dir, "table7_skill_richness_stats.csv"), index=False)

    print("\n=== Table 7: Skill File Richness Statistics ===")
    print(stats_tbl.to_string(index=False))

    # --- Box plots ---
    plot_cols = [c for c, _ in available if c in inst_df.columns]
    plot_labels = [lbl for c, lbl in available if c in inst_df.columns]

    fig, axes = plt.subplots(1, len(plot_cols), figsize=(max(10, len(plot_cols) * 2.5), 5))
    if len(plot_cols) == 1:
        axes = [axes]

    for ax, col, lbl in zip(axes, plot_cols, plot_labels):
        data = inst_df[col].dropna()
        bp = ax.boxplot(data, patch_artist=True, medianprops={"color": "black", "linewidth": 1.5})
        for patch in bp["boxes"]:
            patch.set_facecolor(PALETTE_FOUND)
            patch.set_alpha(0.7)
        ax.set_title(lbl, fontsize=10)
        ax.set_xticks([])
        q50 = data.median()
        ax.text(1.05, q50, f"med={q50:.0f}", va="center", fontsize=8,
                transform=ax.get_yaxis_transform())

    fig.suptitle("Skill File Richness Distribution (SKILL.md Repositories)", y=1.02)

    out_path = os.path.join(out_dir, f"fig8_skill_richness.{fig_format}")
    savefig(fig, out_path, dpi)

    # Bonus: scatter – star count vs skill_count (if stars available)
    if "stars" in inst_df.columns and "skill_count" in inst_df.columns:
        sc_df = inst_df[["stars", "skill_count", "total_files_in_skills"]].dropna()
        if len(sc_df) > 3:
            fig2, ax2 = plt.subplots(figsize=(7, 5))
            sc = ax2.scatter(sc_df["stars"], sc_df["skill_count"],
                             c=sc_df["total_files_in_skills"],
                             cmap="YlOrRd", s=60, alpha=0.7, edgecolors="white")
            plt.colorbar(sc, ax=ax2, label="Total files in skills")
            ax2.set_xlabel("Repository stars")
            ax2.set_ylabel("Number of SKILL.md files")
            ax2.set_title("Repository Popularity vs. SKILL.md Count")
            ax2.set_xscale("symlog")
            out2 = os.path.join(out_dir, f"fig8b_stars_vs_skill_count.{fig_format}")
            savefig(fig2, out2, dpi)

    log.info("Section 8 done.")


# ---------------------------------------------------------------------------
# Section 9: License distribution
# ---------------------------------------------------------------------------

def analyze_license_distribution(df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> None:
    log.info("=== Section 9: License Distribution ===")

    if "license" not in df.columns:
        log.warning("No license column; skipping license analysis.")
        return

    def normalize_license(val: str) -> str:
        if not isinstance(val, str) or not val.strip():
            return "No license"
        v = val.strip()
        # Shorten common names
        mapping = {
            "MIT License": "MIT",
            "Apache License 2.0": "Apache-2.0",
            "GNU General Public License v3.0": "GPL-3.0",
            "GNU General Public License v2.0": "GPL-2.0",
            "BSD 3-Clause \"New\" or \"Revised\" License": "BSD-3-Clause",
            "BSD 2-Clause \"Simplified\" License": "BSD-2-Clause",
            "GNU Lesser General Public License v3.0": "LGPL-3.0",
            "GNU Affero General Public License v3.0": "AGPL-3.0",
        }
        return mapping.get(v, v)

    work = df.copy()
    work["license_norm"] = work["license"].map(normalize_license)

    overall = work["license_norm"].value_counts()
    found_lic = work[work["found"]]["license_norm"].value_counts()

    # Top licenses to plot
    top_lic = overall.head(10).index.tolist()

    lic_tbl = pd.DataFrame({
        "license": top_lic,
        "all_repos": [int(overall.get(l, 0)) for l in top_lic],
        "skill_md_repos": [int(found_lic.get(l, 0)) for l in top_lic],
    })
    lic_tbl["all_pct"] = (100.0 * lic_tbl["all_repos"] / len(work)).round(1)
    n_found = int(work["found"].sum())
    lic_tbl["skill_md_pct"] = (100.0 * lic_tbl["skill_md_repos"] / n_found).round(1) if n_found else 0

    lic_tbl.to_csv(os.path.join(out_dir, "table8_license_distribution.csv"), index=False)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))

    x = np.arange(len(top_lic))
    width = 0.35
    ax0 = axes[0]
    ax0.bar(x - width / 2, lic_tbl["all_pct"], width, label="All repos",
            color=PALETTE_NOT_FOUND, edgecolor="gray")
    ax0.bar(x + width / 2, lic_tbl["skill_md_pct"], width, label="SKILL.md repos",
            color=PALETTE_FOUND, edgecolor="white", alpha=0.85)
    ax0.set_xticks(x)
    ax0.set_xticklabels(top_lic, rotation=40, ha="right", fontsize=9)
    ax0.set_ylabel("Percentage of repos (%)")
    ax0.set_title("License Distribution:\nAll Repos vs. SKILL.md Repos")
    ax0.legend()

    ax1 = axes[1]
    colors_lic = sns.color_palette("Set3", n_colors=len(top_lic))
    wedges, texts, autos = ax1.pie(
        lic_tbl["skill_md_repos"],
        labels=None,
        autopct="%1.1f%%",
        pctdistance=0.75,
        colors=colors_lic,
        startangle=90,
        wedgeprops={"width": 0.55, "edgecolor": "white"},
    )
    for at in autos:
        at.set_fontsize(8)
    ax1.legend(wedges, top_lic, loc="lower center",
               bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=8)
    ax1.set_title("License Breakdown\nfor SKILL.md Repositories")

    out_path = os.path.join(out_dir, f"fig9_license_distribution.{fig_format}")
    savefig(fig, out_path, dpi)
    log.info("Section 9 done.")


# ---------------------------------------------------------------------------
# Section 10: Multi-language ecosystem analysis
# ---------------------------------------------------------------------------

def analyze_language_ecosystem(df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> None:
    """Parse the 'languages' JSON column or fall back to mainLanguage repo counts."""
    log.info("=== Section 10: Language Ecosystem ===")

    def parse_lang_json(val):
        if not isinstance(val, str) or not val.strip():
            return {}
        try:
            return json.loads(val.replace('""', '"'))
        except Exception:
            return {}

    found_df = df[df["found"]].copy()
    all_df = df.copy()

    # Try JSON 'languages' column first; fall back to mainLanguage repo counts
    has_lang_json = (
        "languages" in df.columns
        and df["languages"].notna().any()
        and df["languages"].astype(str).str.strip().replace("", pd.NA).notna().any()
    )

    if has_lang_json:
        def extract_lang_bytes(sub_df):
            lang_bytes: dict[str, int] = {}
            for val in sub_df["languages"]:
                d = parse_lang_json(val)
                for lang, b in d.items():
                    lang_bytes[lang] = lang_bytes.get(lang, 0) + int(b or 0)
            return lang_bytes

        found_lang_bytes = extract_lang_bytes(found_df)
        all_lang_bytes = extract_lang_bytes(all_df)

        if not all_lang_bytes:
            log.warning("Could not parse any language bytes; falling back to mainLanguage counts.")
            has_lang_json = False

    if has_lang_json:
        # --- Byte-volume mode ---
        top_langs = sorted(all_lang_bytes, key=all_lang_bytes.get, reverse=True)[:15]  # type: ignore[arg-type]

        tbl = pd.DataFrame({
            "language": top_langs,
            "all_bytes": [all_lang_bytes.get(l, 0) for l in top_langs],  # type: ignore[union-attr]
            "found_bytes": [found_lang_bytes.get(l, 0) for l in top_langs],  # type: ignore[union-attr]
        })
        tbl["found_share_pct"] = (100.0 * tbl["found_bytes"] / tbl["all_bytes"].replace(0, np.nan)).round(1)
        tbl.to_csv(os.path.join(out_dir, "table9_language_ecosystem.csv"), index=False)

        fig, ax = plt.subplots(figsize=(10, 6))
        x = np.arange(len(top_langs))
        w = 0.4
        ax.bar(x - w / 2, tbl["all_bytes"] / 1e6, w, label="All repos (MB)",
               color=PALETTE_NOT_FOUND, edgecolor="gray")
        ax.bar(x + w / 2, tbl["found_bytes"] / 1e6, w, label="SKILL.md repos (MB)",
               color=PALETTE_FOUND, edgecolor="white", alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(top_langs, rotation=40, ha="right")
        ax.set_ylabel("Code volume (MB)")
        ax.set_title("Language Ecosystem: Code Volume Distribution\n(All Repos vs. SKILL.md Repos)")
        ax.legend()

    else:
        # --- Fallback: repo-count mode using mainLanguage ---
        lang_col = "mainLanguage" if "mainLanguage" in df.columns else None
        if lang_col is None:
            log.warning("No 'languages' or 'mainLanguage' column; skipping ecosystem analysis.")
            return

        log.info("Falling back to mainLanguage repo counts for Fig 10.")

        all_lang = all_df[lang_col].fillna("(unknown)")
        found_lang = found_df[lang_col].fillna("(unknown)")

        all_counts = all_lang.value_counts()
        found_counts_map = found_lang.value_counts()

        top_langs = all_counts.head(15).index.tolist()

        tbl = pd.DataFrame({
            "language": top_langs,
            "all_repos": [int(all_counts.get(l, 0)) for l in top_langs],
            "found_repos": [int(found_counts_map.get(l, 0)) for l in top_langs],
        })
        tbl["found_share_pct"] = (100.0 * tbl["found_repos"] / tbl["all_repos"].replace(0, np.nan)).round(1)
        tbl.to_csv(os.path.join(out_dir, "table9_language_ecosystem.csv"), index=False)

        fig, ax = plt.subplots(figsize=(10, 6))
        x = np.arange(len(top_langs))
        w = 0.4
        ax.bar(x - w / 2, tbl["all_repos"], w, label="All repos",
               color=PALETTE_NOT_FOUND, edgecolor="gray")
        ax.bar(x + w / 2, tbl["found_repos"], w, label="SKILL.md repos",
               color=PALETTE_FOUND, edgecolor="white", alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(top_langs, rotation=40, ha="right")
        ax.set_ylabel("Repository count")
        ax.set_title("Language Ecosystem: Repository Count Distribution\n(All Repos vs. SKILL.md Repos)")
        ax.legend()

    out_path = os.path.join(out_dir, f"fig10_language_ecosystem.{fig_format}")
    savefig(fig, out_path, dpi)
    log.info("Section 10 done.")


# ---------------------------------------------------------------------------
# Section 11: Project maturity indicators
# ---------------------------------------------------------------------------

def analyze_project_maturity(df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> None:
    log.info("=== Section 11: Project Maturity ===")

    found_df = df[df["found"]].copy()
    not_found_df = df[~df["found"]].copy()

    maturity_cols = [
        ("commits", "Total Commits"),
        ("contributors", "Contributors"),
        ("forks", "Forks"),
        ("releases", "Releases"),
        ("totalIssues", "Total Issues"),
    ]
    avail = [(c, l) for c, l in maturity_cols if c in df.columns and df[c].notna().any()]
    if not avail:
        log.warning("No maturity columns available; skipping maturity analysis.")
        return

    # Convert
    for col, _ in avail:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    n_cols = len(avail)
    fig, axes = plt.subplots(1, n_cols, figsize=(n_cols * 3.2, 5))
    if n_cols == 1:
        axes = [axes]

    for ax, (col, label) in zip(axes, avail):
        found_vals = found_df[col].dropna()
        not_found_vals = not_found_df[col].dropna()
        data_to_plot = [found_vals, not_found_vals]
        bp = ax.boxplot(data_to_plot, patch_artist=True,
                        medianprops={"color": "black", "linewidth": 1.5},
                        showfliers=False)
        colors_box = [PALETTE_FOUND, PALETTE_NOT_FOUND]
        for patch, color in zip(bp["boxes"], colors_box):
            patch.set_facecolor(color)
            patch.set_alpha(0.75)
        ax.set_xticks([1, 2])
        ax.set_xticklabels(["SKILL.md", "No SKILL.md"], fontsize=9)
        ax.set_title(label, fontsize=10)
        ax.set_yscale("symlog")

    fig.suptitle("Project Maturity: SKILL.md vs. Non-SKILL.md Repositories\n(outliers hidden for clarity)", y=1.02)

    patches = [
        mpatches.Patch(color=PALETTE_FOUND, label="SKILL.md repos"),
        mpatches.Patch(color=PALETTE_NOT_FOUND, label="Non-SKILL.md repos"),
    ]
    fig.legend(handles=patches, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.05))

    out_path = os.path.join(out_dir, f"fig11_project_maturity.{fig_format}")
    savefig(fig, out_path, dpi)

    # Summary stats comparison table
    rows = []
    for col, label in avail:
        f_s = found_df[col].dropna()
        nf_s = not_found_df[col].dropna()
        rows.append({
            "metric": label,
            "found_median": round(f_s.median(), 1) if len(f_s) else np.nan,
            "found_mean": round(f_s.mean(), 1) if len(f_s) else np.nan,
            "not_found_median": round(nf_s.median(), 1) if len(nf_s) else np.nan,
            "not_found_mean": round(nf_s.mean(), 1) if len(nf_s) else np.nan,
        })
    pd.DataFrame(rows).to_csv(
        os.path.join(out_dir, "table10_project_maturity.csv"), index=False
    )
    log.info("Section 11 done.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="RQ1 analysis: SKILL.md prevalence and adoption across open-source repos."
    )
    p.add_argument("--scan-csv", required=True,
                   help="Main scan results CSV (from B_extract_skill_repos.py)")
    p.add_argument("--instances-csv", default="",
                   help="Optional full_skills_instances CSV (from C_generate_dataset.py)")
    p.add_argument("--out-dir", default="outputs/rq1",
                   help="Output directory for figures and tables (default: outputs/rq1)")
    p.add_argument("--format", dest="fig_format", default="png",
                   choices=["png", "pdf", "svg"],
                   help="Figure output format (default: png)")
    p.add_argument("--dpi", type=int, default=300,
                   help="Figure resolution in DPI (default: 300)")
    p.add_argument("--blacklist", default="blacklist.txt",
                   help="Path to blacklist file (owner/repo per line). Default: blacklist.txt")
    p.add_argument("--name-filter-words", default="",
                   help="Comma-separated words to match against repo names in addition to the "
                        "built-in list. Repos matching any word are excluded.")
    p.add_argument("--no-name-filter", action="store_true",
                   help="Disable the built-in name filter (blacklist still applies).")
    p.add_argument("--log-level", default="INFO",
                   choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args(argv)


def setup_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        stream=sys.stderr,
    )


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    setup_logging(args.log_level)
    setup_style()

    os.makedirs(args.out_dir, exist_ok=True)

    # Build filter configuration
    blacklist = load_blacklist(args.blacklist)
    if args.no_name_filter:
        filter_words: List[str] = []
    else:
        filter_words = list(REPO_NAME_FILTER_WORDS)
        if args.name_filter_words.strip():
            extras = [w.strip() for w in args.name_filter_words.split(",") if w.strip()]
            filter_words.extend(extras)
    log.info(
        "Filters: blacklist=%d entries, name_filter=%d words%s",
        len(blacklist),
        len(filter_words),
        " (disabled)" if args.no_name_filter else "",
    )

    # Load data
    scan_df = load_scan_csv(args.scan_csv, blacklist=blacklist, filter_words=filter_words)
    inst_df = (
        load_instances_csv(args.instances_csv, blacklist=blacklist, filter_words=filter_words)
        if args.instances_csv
        else None
    )

    fmt = args.fig_format
    dpi = args.dpi

    # Run all sections
    analyze_overview(scan_df, args.out_dir)
    analyze_by_language(scan_df, args.out_dir, fmt, dpi)
    analyze_by_size_stars(scan_df, args.out_dir, fmt, dpi)
    analyze_acf_cooccurrence(scan_df, args.out_dir, fmt, dpi)
    analyze_placement_patterns(scan_df, args.out_dir, fmt, dpi)
    analyze_temporal_trend(scan_df, args.out_dir, fmt, dpi)
    analyze_topics(scan_df, args.out_dir, fmt, dpi)

    if inst_df is not None:
        analyze_skill_richness(inst_df, args.out_dir, fmt, dpi)
    else:
        log.warning("No instances CSV provided; skipping skill richness analysis (Section 8).")

    analyze_license_distribution(scan_df, args.out_dir, fmt, dpi)
    analyze_language_ecosystem(scan_df, args.out_dir, fmt, dpi)
    analyze_project_maturity(scan_df, args.out_dir, fmt, dpi)

    print(f"\nAll outputs written to: {os.path.abspath(args.out_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
