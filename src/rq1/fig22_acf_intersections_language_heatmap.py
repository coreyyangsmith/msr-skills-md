from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import (
    add_output_args,
    add_scan_input_args,
    configure_logging,
    load_scan_csv,
    resolve_filters,
    savefig,
    setup_style,
    write_dataframe,
    write_missing_data_note,
)
from rq1.fig3_acf_cooccurrence import ACF_COLUMNS

log = logging.getLogger(__name__)


def _present_acf_columns(scan_df: pd.DataFrame) -> list[str]:
    return [column for column in ACF_COLUMNS if column in scan_df.columns]


def _prepare_found_df(scan_df: pd.DataFrame, present: list[str]) -> pd.DataFrame:
    found_df = scan_df[scan_df["found"]].copy()
    for column in present:
        found_df[column] = pd.to_numeric(found_df[column], errors="coerce").fillna(0).astype(int)
    found_df["language"] = found_df.get("mainLanguage", pd.Series(dtype=str)).fillna("(unknown)")
    found_df["language"] = found_df["language"].replace("", "(unknown)")
    return found_df


def _short_artifact(label: str) -> str:
    return (
        label.replace("copilot-instructions.md", "copilot")
        .replace("CLAUDE.md", "CLAUDE")
        .replace("AGENTS.md", "AGENTS")
        .replace(".md", "")
    )


def _build_intersection_table(found_df: pd.DataFrame, present: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for _, row in found_df.iterrows():
        active = [column for column in present if int(row[column]) == 1]
        active_labels = [ACF_COLUMNS[column] for column in active]
        rows.append(
            {
                "active_columns": tuple(active),
                "combination": "SKILL.md only" if not active else " + ".join(active_labels),
            }
        )

    combo_counts = pd.DataFrame(rows).value_counts(["active_columns", "combination"]).reset_index(name="count")
    combo_counts["pct_of_skill_md_repos"] = 100.0 * combo_counts["count"] / len(found_df)
    combo_counts["artifact_count"] = combo_counts["active_columns"].apply(len)
    return combo_counts.sort_values(["count", "artifact_count", "combination"], ascending=[False, True, True]).reset_index(drop=True)


def _build_language_table(found_df: pd.DataFrame, present: list[str]) -> pd.DataFrame:
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
                    "pct_of_skill_md_repos": 100.0 * count / total if total else 0.0,
                }
            )
    return pd.DataFrame(rows)


def _plot_upset(panel_spec, fig: plt.Figure, combo_df: pd.DataFrame, present: list[str]) -> None:
    inner = panel_spec.subgridspec(2, 1, height_ratios=[3.0, 1.35], hspace=0.06)
    ax_bar = fig.add_subplot(inner[0])
    ax_matrix = fig.add_subplot(inner[1], sharex=ax_bar)

    plot_df = combo_df.head(10).copy()
    x = np.arange(len(plot_df))
    counts = plot_df["count"].astype(int).to_numpy()
    total = int(combo_df["count"].sum())

    bars = ax_bar.bar(x, counts, color="#42A5F5", edgecolor="white", width=0.68)
    ax_bar.set_title("(a) Exact ACF Co-occurrence Patterns", fontsize=15, fontweight="bold", pad=10)
    ax_bar.set_ylabel("Repositories", fontsize=12, fontweight="bold")
    ax_bar.tick_params(axis="x", labelbottom=False)
    ax_bar.tick_params(axis="y", labelsize=10)
    ax_bar.grid(axis="y", color="#d0d0d0", linewidth=0.8, alpha=0.55)
    ax_bar.grid(axis="x", visible=False)
    ax_bar.spines["top"].set_visible(False)
    ax_bar.spines["right"].set_visible(False)

    y_offset = max(counts.max() * 0.025, 2)
    for index, (bar, row) in enumerate(zip(bars, plot_df.itertuples(index=False))):
        ax_bar.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + y_offset,
            f"{int(row.count):,}\n({row.pct_of_skill_md_repos:.1f}%)",
            ha="center",
            va="bottom",
            fontsize=8.5,
            fontweight="bold",
            linespacing=1.15,
        )
        if index < 3:
            ax_bar.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + y_offset * 6.2,
                row.combination.replace(" + ", "\n+ "),
                ha="center",
                va="bottom",
                fontsize=8,
                color="#444444",
                linespacing=1.05,
            )

    ax_bar.set_ylim(0, counts.max() * 1.34)

    set_labels = [ACF_COLUMNS[column] for column in present]
    set_y = np.arange(len(present))[::-1]
    ax_matrix.set_yticks(set_y)
    ax_matrix.set_yticklabels([_short_artifact(label) for label in set_labels], fontsize=9)
    ax_matrix.set_ylim(-0.8, len(present) - 0.2)
    ax_matrix.set_xlim(-0.55, len(plot_df) - 0.45)
    ax_matrix.tick_params(axis="x", length=0)
    ax_matrix.tick_params(axis="y", length=0)
    ax_matrix.spines["top"].set_visible(False)
    ax_matrix.spines["right"].set_visible(False)
    ax_matrix.spines["left"].set_visible(False)
    ax_matrix.spines["bottom"].set_visible(False)

    for col_index, row in enumerate(plot_df.itertuples(index=False)):
        active_columns = set(row.active_columns)
        active_ys: list[int] = []
        for row_index, column in enumerate(present):
            y_value = set_y[row_index]
            is_active = column in active_columns
            ax_matrix.scatter(
                col_index,
                y_value,
                s=58 if is_active else 34,
                color="#1f1f1f" if is_active else "#d9d9d9",
                zorder=3,
            )
            if is_active:
                active_ys.append(y_value)
        if len(active_ys) >= 2:
            ax_matrix.plot([col_index, col_index], [min(active_ys), max(active_ys)], color="#1f1f1f", linewidth=1.7, zorder=2)

    x_labels = [
        "SKILL\nonly"
        if len(row.active_columns) == 0
        else "\n+".join(_short_artifact(ACF_COLUMNS[column]) for column in row.active_columns)
        for row in plot_df.itertuples(index=False)
    ]
    ax_matrix.set_xticks(x)
    ax_matrix.set_xticklabels(x_labels, fontsize=8, rotation=0)
    ax_matrix.set_xlabel(f"Exact artifact combination among {total:,} SKILL.md repositories", fontsize=10, fontweight="bold", labelpad=8)


def _plot_language_heatmap(ax: plt.Axes, language_df: pd.DataFrame) -> None:
    language_order = (
        language_df[["language", "skill_md_repo_count"]]
        .drop_duplicates()
        .sort_values("skill_md_repo_count", ascending=False)["language"]
        .tolist()
    )
    artifact_order = (
        language_df.groupby("artifact")["count"]
        .sum()
        .sort_values(ascending=False)
        .index.tolist()
    )
    heat_data = language_df.pivot_table(
        index="language",
        columns="artifact",
        values="pct_of_skill_md_repos",
        observed=True,
    ).reindex(index=language_order, columns=artifact_order)

    annot = heat_data.map(lambda value: f"{value:.1f}%" if pd.notna(value) else "")
    sns.heatmap(
        heat_data,
        annot=annot,
        fmt="",
        cmap="Blues",
        vmin=0,
        vmax=max(50.0, float(np.nanmax(heat_data.to_numpy()))),
        linewidths=0.5,
        linecolor="white",
        cbar_kws={"label": "% of SKILL.md repos"},
        annot_kws={"size": 8.5, "weight": "bold"},
        ax=ax,
    )
    ax.set_title("(b) ACF Prevalence by Language", fontsize=15, fontweight="bold", pad=10)
    ax.set_xlabel("Tracked ACF", fontsize=12, fontweight="bold")
    ax.set_ylabel("Primary language", fontsize=12, fontweight="bold")
    ax.set_xticklabels([_short_artifact(label) for label in artifact_order], rotation=25, ha="right", fontsize=9)
    ax.set_yticklabels(ax.get_yticklabels(), rotation=0, fontsize=9)


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    candidate_columns = _present_acf_columns(scan_df)
    if "found" not in scan_df.columns or not candidate_columns:
        write_missing_data_note(
            out_dir,
            "fig22_acf_intersections_language_heatmap",
            "No usable SKILL.md or tracked ACF columns were available for Figure 22.",
            missing_columns=["found", *ACF_COLUMNS.keys()],
        )
        return None

    found_df = _prepare_found_df(scan_df, candidate_columns)
    if found_df.empty:
        write_missing_data_note(
            out_dir,
            "fig22_acf_intersections_language_heatmap",
            "No repositories containing SKILL.md were available for Figure 22.",
            missing_columns=["found"],
        )
        return None

    present = [column for column in candidate_columns if int(found_df[column].sum()) > 0]
    if not present:
        write_missing_data_note(
            out_dir,
            "fig22_acf_intersections_language_heatmap",
            "No tracked ACF columns had positive counts for Figure 22.",
            missing_columns=list(ACF_COLUMNS.keys()),
        )
        return None

    combo_df = _build_intersection_table(found_df, present)
    language_df = _build_language_table(found_df, present)
    write_dataframe(combo_df.drop(columns=["active_columns"]), str(Path(out_dir) / "table22_acf_intersections.csv"))
    write_dataframe(language_df, str(Path(out_dir) / "table22_acf_language_heatmap.csv"))

    fig = plt.figure(figsize=(16.8, 6.2), constrained_layout=True)
    outer = fig.add_gridspec(1, 2, width_ratios=[1.18, 1.0], wspace=0.22)
    _plot_upset(outer[0], fig, combo_df, present)
    ax_heatmap = fig.add_subplot(outer[1])
    _plot_language_heatmap(ax_heatmap, language_df)

    output_path = Path(out_dir) / f"fig22_acf_intersections_language_heatmap.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 22 for RQ1")
    add_scan_input_args(parser)
    add_output_args(parser)
    args = parser.parse_args(argv)

    configure_logging(args.log_level)
    setup_style()
    blacklist, filter_words = resolve_filters(args)
    scan_df = load_scan_csv(args.scan_csv, blacklist=blacklist, filter_words=filter_words)
    generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
