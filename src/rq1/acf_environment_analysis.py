from __future__ import annotations

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from rq1.common import savefig, write_dataframe
from rq1.fig3_acf_cooccurrence import ACF_COLUMNS

log = logging.getLogger(__name__)


def _present_acf_columns(scan_df: pd.DataFrame) -> list[str]:
    return [column for column in ACF_COLUMNS if column in scan_df.columns]


def build_availability_table(scan_df: pd.DataFrame) -> pd.DataFrame:
    found_rows = int(scan_df["found"].sum()) if "found" in scan_df.columns else 0
    total_rows = len(scan_df)
    rows: list[dict[str, object]] = []
    for column, artifact in ACF_COLUMNS.items():
        present = column in scan_df.columns
        rows.append(
            {
                "artifact": artifact,
                "scan_column": column,
                "column_present_in_scan_csv": present,
                "repos_in_dataset": total_rows,
                "skill_md_repos_in_dataset": found_rows,
                "usable_with_current_data_for_skill_repo_analysis": present,
                "usable_with_current_data_for_preference_question": False,
                "new_data_required": (not present) or True,
                "reason": (
                    "Column missing from current scan outputs."
                    if not present
                    else "ACF checks were only executed for SKILL.md repos, so non-SKILL rows cannot support prevalence-by-environment estimation."
                ),
            }
        )
    return pd.DataFrame(rows)


def prepare_found_acf_df(scan_df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    present = _present_acf_columns(scan_df)
    if "found" not in scan_df.columns:
        return pd.DataFrame(), present

    found_df = scan_df[scan_df["found"]].copy()
    if found_df.empty:
        return found_df, present

    for column in present:
        found_df[column] = pd.to_numeric(found_df[column], errors="coerce").fillna(0).astype(int)

    found_df["language"] = found_df.get("mainLanguage", pd.Series(dtype=str)).fillna("(unknown)")
    found_df["language"] = found_df["language"].replace("", "(unknown)")
    return found_df, present


def build_overall_table(found_df: pd.DataFrame, present: list[str]) -> pd.DataFrame:
    total = len(found_df)
    rows = []
    for column in present:
        count = int(found_df[column].sum())
        rows.append(
            {
                "artifact": ACF_COLUMNS[column],
                "count": count,
                "pct_of_skill_md_repos": round(100.0 * count / total, 2) if total else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("count", ascending=False)


def build_language_table(found_df: pd.DataFrame, present: list[str]) -> pd.DataFrame:
    totals = found_df.groupby("language").size().rename("skill_md_repo_count")
    rows: list[dict[str, object]] = []
    for language, total in totals.items():
        subset = found_df[found_df["language"] == language]
        for column in present:
            count = int(subset[column].sum())
            rows.append(
                {
                    "language": language,
                    "artifact": ACF_COLUMNS[column],
                    "count": count,
                    "skill_md_repo_count": int(total),
                    "pct_of_skill_md_repos": round(100.0 * count / total, 2) if total else 0.0,
                }
            )
    return pd.DataFrame(rows).sort_values(["skill_md_repo_count", "artifact"], ascending=[False, True])


def _phi_coefficient(a: int, b: int, c: int, d: int) -> float:
    denom = np.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    if denom == 0:
        return 0.0
    return float((a * d - b * c) / denom)


def build_pairwise_table(found_df: pd.DataFrame, present: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    n = len(found_df)
    for i, first in enumerate(present):
        set_first = found_df[first].astype(bool)
        count_first = int(set_first.sum())
        for second in present[i:]:
            set_second = found_df[second].astype(bool)
            count_second = int(set_second.sum())
            both = int((set_first & set_second).sum())
            union = int((set_first | set_second).sum())
            only_first = count_first - both
            only_second = count_second - both
            neither = n - both - only_first - only_second
            expected = (count_first * count_second / n) if n else 0.0
            rows.append(
                {
                    "artifact_a": ACF_COLUMNS[first],
                    "artifact_b": ACF_COLUMNS[second],
                    "count_a": count_first,
                    "count_b": count_second,
                    "intersection_count": both,
                    "union_count": union,
                    "jaccard": round(both / union, 4) if union else 0.0,
                    "conditional_b_given_a": round(both / count_first, 4) if count_first else 0.0,
                    "conditional_a_given_b": round(both / count_second, 4) if count_second else 0.0,
                    "lift": round((both / n) / ((count_first / n) * (count_second / n)), 4)
                    if n and count_first and count_second
                    else 0.0,
                    "phi": round(_phi_coefficient(both, only_first, only_second, neither), 4),
                    "expected_intersection_if_independent": round(expected, 2),
                }
            )
    return pd.DataFrame(rows)


def build_combination_table(found_df: pd.DataFrame, present: list[str]) -> pd.DataFrame:
    total = len(found_df)
    rows = []
    for _, row in found_df.iterrows():
        active = [ACF_COLUMNS[column] for column in present if int(row[column]) == 1]
        label = "None of the tracked artifacts" if not active else " + ".join(active)
        rows.append(label)

    combo_counts = pd.Series(rows).value_counts().rename_axis("combination").reset_index(name="count")
    combo_counts["pct_of_skill_md_repos"] = combo_counts["count"].apply(
        lambda value: round(100.0 * value / total, 2) if total else 0.0
    )
    return combo_counts


def build_count_distribution_table(found_df: pd.DataFrame, present: list[str]) -> pd.DataFrame:
    total = len(found_df)
    counts = found_df[present].sum(axis=1).astype(int) if present else pd.Series(dtype=int)
    rows: list[dict[str, object]] = []
    for tracked_count in range(0, len(present) + 1):
        repo_count = int((counts == tracked_count).sum())
        rows.append(
            {
                "tracked_artifact_count": tracked_count,
                "label": f"{tracked_count} tracked artifact" + ("" if tracked_count == 1 else "s"),
                "count": repo_count,
                "pct_of_skill_md_repos": round(100.0 * repo_count / total, 2) if total else 0.0,
            }
        )
    return pd.DataFrame(rows)


def build_language_summary_table(found_df: pd.DataFrame, present: list[str]) -> pd.DataFrame:
    if found_df.empty:
        return pd.DataFrame()

    tracked_counts = found_df[present].sum(axis=1).astype(int) if present else pd.Series(dtype=int)
    working_df = found_df.copy()
    working_df["tracked_artifact_count"] = tracked_counts

    rows: list[dict[str, object]] = []
    for language, subset in working_df.groupby("language"):
        total = len(subset)
        any_count = int((subset["tracked_artifact_count"] >= 1).sum())
        multi_count = int((subset["tracked_artifact_count"] >= 2).sum())
        all_count = int((subset["tracked_artifact_count"] == len(present)).sum()) if present else 0
        rows.append(
            {
                "language": language,
                "skill_md_repo_count": total,
                "repos_with_any_tracked_acf": any_count,
                "pct_with_any_tracked_acf": round(100.0 * any_count / total, 2) if total else 0.0,
                "repos_with_multiple_tracked_acfs": multi_count,
                "pct_with_multiple_tracked_acfs": round(100.0 * multi_count / total, 2) if total else 0.0,
                "repos_with_all_tracked_acfs": all_count,
                "pct_with_all_tracked_acfs": round(100.0 * all_count / total, 2) if total else 0.0,
            }
        )

    return pd.DataFrame(rows).sort_values("skill_md_repo_count", ascending=False)


def plot_language_prevalence(language_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    if language_df.empty:
        return None
    top_languages = (
        language_df[["language", "skill_md_repo_count"]]
        .drop_duplicates()
        .sort_values("skill_md_repo_count", ascending=False)
        .head(10)["language"]
        .tolist()
    )
    plot_df = language_df[language_df["language"].isin(top_languages)].copy()
    fig, ax = plt.subplots(figsize=(11, 5.8))
    sns.barplot(data=plot_df, x="language", y="pct_of_skill_md_repos", hue="artifact", ax=ax)
    ax.set_title("Tracked ACF Usage by Primary Language\n(SKILL.md repos only)")
    ax.set_xlabel("")
    ax.set_ylabel("% of SKILL.md repos in language")
    ax.tick_params(axis="x", rotation=20)
    ax.legend(title="Artifact", fontsize=9, title_fontsize=10)
    output_path = Path(out_dir) / f"fig15_acf_prevalence_by_language.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def plot_pairwise_jaccard(pairwise_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    if pairwise_df.empty:
        return None
    labels = sorted(set(pairwise_df["artifact_a"]) | set(pairwise_df["artifact_b"]))
    matrix = pd.DataFrame(0.0, index=labels, columns=labels)
    for _, row in pairwise_df.iterrows():
        matrix.loc[row["artifact_a"], row["artifact_b"]] = row["jaccard"]
        matrix.loc[row["artifact_b"], row["artifact_a"]] = row["jaccard"]

    fig, ax = plt.subplots(figsize=(6.8, 5.6))
    sns.heatmap(
        matrix,
        annot=True,
        fmt=".2f",
        cmap="Blues",
        vmin=0,
        vmax=1,
        linewidths=0.5,
        cbar_kws={"label": "Jaccard similarity"},
        ax=ax,
    )
    ax.set_title("Tracked ACF Pairwise Co-occurrence Similarity\n(SKILL.md repos only)")
    output_path = Path(out_dir) / f"fig16_acf_pairwise_jaccard_heatmap.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def plot_conditional_heatmap(pairwise_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    if pairwise_df.empty:
        return None
    labels = sorted(set(pairwise_df["artifact_a"]) | set(pairwise_df["artifact_b"]))
    matrix = pd.DataFrame(0.0, index=labels, columns=labels)
    for label in labels:
        matrix.loc[label, label] = 1.0
    for _, row in pairwise_df.iterrows():
        matrix.loc[row["artifact_a"], row["artifact_b"]] = row["conditional_b_given_a"]
        matrix.loc[row["artifact_b"], row["artifact_a"]] = row["conditional_a_given_b"]

    fig, ax = plt.subplots(figsize=(6.8, 5.6))
    sns.heatmap(
        matrix,
        annot=True,
        fmt=".2f",
        cmap="YlGnBu",
        vmin=0,
        vmax=1,
        linewidths=0.5,
        cbar_kws={"label": "Conditional probability"},
        ax=ax,
    )
    ax.set_title("P(Column Artifact | Row Artifact)\n(SKILL.md repos only)")
    output_path = Path(out_dir) / f"fig17_acf_conditional_probability_heatmap.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def plot_combination_distribution(combo_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    if combo_df.empty:
        return None
    plot_df = combo_df.head(10).sort_values("count", ascending=True)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(plot_df["combination"], plot_df["count"], color="#5C6BC0", edgecolor="white")
    ax.set_title("Most Common Tracked ACF Combinations\n(SKILL.md repos only)")
    ax.set_xlabel("Repository count")
    ax.set_ylabel("")
    for _, row in plot_df.iterrows():
        ax.text(row["count"] + 5, row["combination"], f"{row['count']} ({row['pct_of_skill_md_repos']:.1f}%)", va="center", fontsize=9)
    output_path = Path(out_dir) / f"fig18_acf_combination_distribution.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def plot_count_distribution(count_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    if count_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        count_df["label"],
        count_df["count"],
        color=["#CFD8DC", "#90CAF9", "#4FC3F7", "#26A69A"][: len(count_df)],
        edgecolor="white",
    )
    ax.set_title("How Many Tracked ACFs Appear per SKILL.md Repository?")
    ax.set_xlabel("")
    ax.set_ylabel("Repository count")
    ax.tick_params(axis="x", rotation=10)
    upper = max(count_df["count"].max() * 1.12, 1)
    ax.set_ylim(0, upper)

    for bar, row in zip(bars, count_df.to_dict("records")):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + upper * 0.015,
            f"{int(row['count'])}\n({row['pct_of_skill_md_repos']:.1f}%)",
            ha="center",
            va="bottom",
            fontsize=9,
        )

    output_path = Path(out_dir) / f"fig19_acf_count_distribution.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def plot_language_adoption_summary(
    language_summary_df: pd.DataFrame,
    out_dir: str,
    fig_format: str,
    dpi: int,
) -> Path | None:
    if language_summary_df.empty:
        return None

    plot_df = language_summary_df.head(10).copy()
    x = np.arange(len(plot_df))
    width = 0.24
    series = [
        ("pct_with_any_tracked_acf", "Any tracked ACF", "#42A5F5"),
        ("pct_with_multiple_tracked_acfs", "2+ tracked ACFs", "#26A69A"),
        ("pct_with_all_tracked_acfs", "All tracked ACFs", "#7E57C2"),
    ]

    fig, ax = plt.subplots(figsize=(11, 5.8))
    for idx, (column, label, color) in enumerate(series):
        offsets = x + (idx - 1) * width
        bars = ax.bar(offsets, plot_df[column], width=width, label=label, color=color, edgecolor="white")
        for bar, value in zip(bars, plot_df[column]):
            if value <= 0:
                continue
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 1.0,
                f"{value:.1f}%",
                ha="center",
                va="bottom",
                fontsize=8,
                rotation=90,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(plot_df["language"], rotation=20, ha="right")
    ax.set_ylim(0, max(plot_df["pct_with_any_tracked_acf"].max() * 1.18, 10))
    ax.set_ylabel("% of SKILL.md repos in language")
    ax.set_xlabel("")
    ax.set_title("Tracked ACF Adoption Intensity by Primary Language\n(SKILL.md repos only)")
    ax.legend(title="Measure", fontsize=9, title_fontsize=10)

    output_path = Path(out_dir) / f"fig20_acf_any_multi_by_language.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def write_analysis_note(
    availability_df: pd.DataFrame,
    overall_df: pd.DataFrame,
    pairwise_df: pd.DataFrame,
    combo_df: pd.DataFrame,
    count_df: pd.DataFrame,
    language_summary_df: pd.DataFrame,
    out_dir: str,
) -> Path:
    lines = [
        "# RQ1 ACF Environment Analysis",
        "",
        "## Data Availability",
        "- Current scan data can support co-occurrence analysis among tracked ACFs inside confirmed `SKILL.md` repositories.",
        "- Current scan data cannot support a clean estimate of whether developers in a given environment prefer `SKILL.md`, because tracked ACF checks were only executed for `found=true` repositories.",
        "- `.cursorrules.md` is not available as a structured column in the current scan CSV, so answering questions about that artifact requires a new scan/enrichment pass.",
        "- The local `outputs/raw_data` mirror also lines up with the SKILL.md-positive subset rather than the full scanned population, so it cannot backfill the missing negative cases for a preference comparison.",
        "",
        "## Overall Findings on Tracked ACFs within SKILL.md Repositories",
    ]
    for _, row in overall_df.iterrows():
        lines.append(
            f"- `{row['artifact']}` appears in `{int(row['count'])}` repos "
            f"({row['pct_of_skill_md_repos']:.2f}% of SKILL.md repos)."
        )

    if not count_df.empty:
        any_row = count_df[count_df["tracked_artifact_count"] >= 1]["count"].sum()
        multi_row = count_df[count_df["tracked_artifact_count"] >= 2]["count"].sum()
        all_row = count_df[count_df["tracked_artifact_count"] == count_df["tracked_artifact_count"].max()]["count"].sum()
        total = int(count_df["count"].sum())
        lines.extend(
            [
                "",
                "## How Often Multiple ACFs Appear",
                f"- At least one tracked ACF appears in `{int(any_row)}` repos ({(100.0 * any_row / total):.2f}% of SKILL.md repos).",
                f"- Multiple tracked ACFs (2+) appear in `{int(multi_row)}` repos ({(100.0 * multi_row / total):.2f}% of SKILL.md repos).",
                f"- All tracked ACFs appear together in `{int(all_row)}` repos ({(100.0 * all_row / total):.2f}% of SKILL.md repos).",
            ]
        )

    if not pairwise_df.empty:
        off_diag = pairwise_df[pairwise_df["artifact_a"] != pairwise_df["artifact_b"]].copy()
        top_jaccard = off_diag.sort_values("jaccard", ascending=False).head(3)
        top_lift = off_diag.sort_values("lift", ascending=False).head(3)
        lines.extend(
            [
                "",
                "## Pairwise Co-occurrence",
                "Strongest pairwise overlaps by Jaccard:",
            ]
        )
        for _, row in top_jaccard.iterrows():
            lines.append(
                f"- `{row['artifact_a']}` + `{row['artifact_b']}`: "
                f"intersection `{int(row['intersection_count'])}`, jaccard `{row['jaccard']:.4f}`"
            )
        lines.append("")
        lines.append("Strongest pairwise associations by lift:")
        for _, row in top_lift.iterrows():
            lines.append(
                f"- `{row['artifact_a']}` -> `{row['artifact_b']}`: "
                f"lift `{row['lift']:.4f}`, P(B|A) `{row['conditional_b_given_a']:.4f}`"
            )

    if not combo_df.empty:
        lines.extend(
            [
                "",
                "## Combination Usage",
                "Most common tracked-artifact combinations:",
            ]
        )
        for _, row in combo_df.head(5).iterrows():
            lines.append(
                f"- `{row['combination']}`: `{int(row['count'])}` repos "
                f"({row['pct_of_skill_md_repos']:.2f}%)"
            )

    if not language_summary_df.empty:
        top_any = language_summary_df.sort_values("pct_with_any_tracked_acf", ascending=False).head(3)
        top_multi = language_summary_df.sort_values("pct_with_multiple_tracked_acfs", ascending=False).head(3)
        lines.extend(
            [
                "",
                "## Language-Level Pattern Differences",
                "Highest shares of SKILL.md repos with any tracked ACF:",
            ]
        )
        for _, row in top_any.iterrows():
            lines.append(
                f"- `{row['language']}`: `{row['pct_with_any_tracked_acf']:.2f}%` "
                f"({int(row['repos_with_any_tracked_acf'])}/{int(row['skill_md_repo_count'])})"
            )
        lines.append("")
        lines.append("Highest shares of SKILL.md repos with multiple tracked ACFs:")
        for _, row in top_multi.iterrows():
            lines.append(
                f"- `{row['language']}`: `{row['pct_with_multiple_tracked_acfs']:.2f}%` "
                f"({int(row['repos_with_multiple_tracked_acfs'])}/{int(row['skill_md_repo_count'])})"
            )

    output_path = Path(out_dir) / "note_rq1_acf_environment_analysis.md"
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info("Saved note: %s", output_path)
    return output_path


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    availability_df = build_availability_table(scan_df)
    write_dataframe(availability_df, str(Path(out_dir) / "table5_acf_data_availability.csv"))

    found_df, present = prepare_found_acf_df(scan_df)
    if found_df.empty or not present:
        log.warning("No usable ACF columns found for environment analysis.")
        return write_analysis_note(
            availability_df,
            pd.DataFrame(columns=["artifact", "count", "pct_of_skill_md_repos"]),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            out_dir,
        )

    overall_df = build_overall_table(found_df, present)
    language_df = build_language_table(found_df, present)
    pairwise_df = build_pairwise_table(found_df, present)
    combo_df = build_combination_table(found_df, present)
    count_df = build_count_distribution_table(found_df, present)
    language_summary_df = build_language_summary_table(found_df, present)

    write_dataframe(overall_df, str(Path(out_dir) / "table6_acf_overall_prevalence.csv"))
    write_dataframe(language_df, str(Path(out_dir) / "table7_acf_language_breakdown.csv"))
    write_dataframe(pairwise_df, str(Path(out_dir) / "table8_acf_pairwise_association.csv"))
    write_dataframe(combo_df, str(Path(out_dir) / "table9_acf_combination_distribution.csv"))
    write_dataframe(count_df, str(Path(out_dir) / "table14_acf_count_distribution.csv"))
    write_dataframe(language_summary_df, str(Path(out_dir) / "table15_acf_language_adoption_summary.csv"))

    plot_language_prevalence(language_df, out_dir, fig_format, dpi)
    plot_pairwise_jaccard(pairwise_df, out_dir, fig_format, dpi)
    plot_conditional_heatmap(pairwise_df, out_dir, fig_format, dpi)
    plot_combination_distribution(combo_df, out_dir, fig_format, dpi)
    plot_count_distribution(count_df, out_dir, fig_format, dpi)
    plot_language_adoption_summary(language_summary_df, out_dir, fig_format, dpi)

    return write_analysis_note(
        availability_df,
        overall_df,
        pairwise_df,
        combo_df,
        count_df,
        language_summary_df,
        out_dir,
    )
