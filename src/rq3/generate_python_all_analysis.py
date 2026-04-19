#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from rq1.common import configure_logging, savefig, setup_style, write_dataframe
from rq3.label_processing import INSTRUCTION_TYPE_LABELS, SDLC_STAGE_LABELS

log = logging.getLogger(__name__)

DEFAULT_A_FILE = "2026-04-06_CY_Labels_A_Python.json"
DEFAULT_B_FILE = "2026-04-06_MV_Labels_B_Python.json"
DEFAULT_BOTH_FILE = "2026-04-02_CY_Labels_Both_Python.json"
DEFAULT_ALL_FILE = "Python_All.json"


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def display_name(file_name: str) -> str:
    if file_name == DEFAULT_A_FILE:
        return "Python A"
    if file_name == DEFAULT_B_FILE:
        return "Python B"
    if file_name == DEFAULT_BOTH_FILE:
        return "Python Both"
    if file_name == DEFAULT_ALL_FILE:
        return "Python All"
    return Path(file_name).stem


def load_dataset_stats(processed_dir: Path, file_names: list[str]) -> dict[str, dict]:
    stats = load_json(processed_dir / "processed_label_statistics.json")
    by_file = {item["file"]: item for item in stats.get("datasets", [])}
    missing = [file_name for file_name in file_names if file_name not in by_file]
    if missing:
        raise SystemExit(f"Missing dataset stats for: {', '.join(missing)}")
    return {file_name: by_file[file_name] for file_name in file_names}


def build_summary_table(dataset_map: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for file_name, stats in dataset_map.items():
        rows.append(
            {
                "file": file_name,
                "dataset": display_name(file_name),
                "retained_documents": stats["retained_documents"],
                "filtered_documents": stats["filtered_documents"],
                "total_documents": stats["total_documents"],
                "retained_pct": stats["retained_pct"],
                "filtered_pct": stats["filtered_pct"],
                "avg_labels_per_retained_document": stats["average_labels_per_retained_document"],
                "avg_labels_per_filtered_document": stats["average_labels_per_filtered_document"],
                "filter_source_document_counts": stats.get("filter_source_document_counts", {}),
            }
        )
    return pd.DataFrame(rows)


def build_distribution_table(
    dataset_map: dict[str, dict],
    distribution_key: str,
    labels: tuple[str, ...] | list[str],
) -> pd.DataFrame:
    rows = []
    for file_name, stats in dataset_map.items():
        distribution = stats.get(distribution_key, {})
        for label in labels:
            entry = distribution.get(label, {})
            rows.append(
                {
                    "file": file_name,
                    "dataset": display_name(file_name),
                    "label": label,
                    "count": entry.get("count", 0),
                    "pct_docs": entry.get("pct_docs", 0.0),
                    "retained_documents": stats["retained_documents"],
                }
            )
    return pd.DataFrame(rows)


def build_filter_source_table(dataset_map: dict[str, dict]) -> pd.DataFrame:
    rows = []
    for file_name, stats in dataset_map.items():
        for filter_source, count in stats.get("filter_source_document_counts", {}).items():
            rows.append(
                {
                    "file": file_name,
                    "dataset": display_name(file_name),
                    "filter_source": filter_source,
                    "count": count,
                }
            )
    return pd.DataFrame(rows)


def build_python_all_heatmap_table(dataset_map: dict[str, dict]) -> pd.DataFrame:
    stats = dataset_map[DEFAULT_ALL_FILE]
    matrix = stats.get("instruction_x_sdlc_stage_retained", {})
    rows = []
    for instruction in INSTRUCTION_TYPE_LABELS:
        for stage in SDLC_STAGE_LABELS:
            rows.append(
                {
                    "instruction_type": instruction,
                    "sdlc_stage": stage,
                    "count": matrix.get(instruction, {}).get(stage, 0),
                }
            )
    return pd.DataFrame(rows)


def plot_grouped_percent_bars(
    df: pd.DataFrame,
    *,
    title: str,
    output_path: Path,
    dpi: int,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.8))
    sns.barplot(data=df, x="label", y="pct_docs", hue="dataset", ax=ax)
    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel("% of retained docs")
    ax.tick_params(axis="x", rotation=22)
    ax.legend(title="Dataset", fontsize=9, title_fontsize=10)
    savefig(fig, str(output_path), dpi)


def plot_python_all_focus(
    df: pd.DataFrame,
    *,
    title: str,
    color: str,
    output_path: Path,
    dpi: int,
) -> None:
    plot_df = df[df["dataset"] == "Python All"].sort_values("pct_docs", ascending=True)
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.barh(plot_df["label"], plot_df["pct_docs"], color=color, edgecolor="white")
    ax.set_xlabel("% of retained docs")
    ax.set_ylabel("")
    ax.set_title(title)
    for _, row in plot_df.iterrows():
        ax.text(row["pct_docs"] + 1.2, row["label"], f"{row['count']} ({row['pct_docs']:.1f}%)", va="center", fontsize=9)
    savefig(fig, str(output_path), dpi)


def plot_retained_vs_filtered(summary_df: pd.DataFrame, output_path: Path, dpi: int) -> None:
    plot_df = summary_df.copy()
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    ax.bar(plot_df["dataset"], plot_df["retained_documents"], color="#4CAF50", label="Retained")
    ax.bar(
        plot_df["dataset"],
        plot_df["filtered_documents"],
        bottom=plot_df["retained_documents"],
        color="#FF8A65",
        label="Filtered",
    )
    ax.set_ylabel("Document count")
    ax.set_xlabel("")
    ax.set_title("Python Dataset Sources\nRetained vs Filtered Documents")
    ax.legend(loc="upper right")
    ax.tick_params(axis="x", rotation=12)
    for _, row in plot_df.iterrows():
        ax.text(
            row.name,
            row["total_documents"] + 3,
            f"{row['filtered_pct']:.1f}% filtered",
            ha="center",
            fontsize=9,
        )
    savefig(fig, str(output_path), dpi)


def plot_filter_sources(filter_df: pd.DataFrame, output_path: Path, dpi: int) -> None:
    pivot = filter_df.pivot(index="dataset", columns="filter_source", values="count").fillna(0)
    fig, ax = plt.subplots(figsize=(8.8, 5.4))
    pivot.plot(
        kind="bar",
        stacked=True,
        ax=ax,
        color=["#5C6BC0", "#FFB74D", "#EF5350"],
        edgecolor="white",
    )
    ax.set_ylabel("Filtered document count")
    ax.set_xlabel("")
    ax.set_title("Python Dataset Sources\nFilter Source Breakdown")
    ax.legend(title="Original filter source", fontsize=9, title_fontsize=10)
    ax.tick_params(axis="x", rotation=12)
    savefig(fig, str(output_path), dpi)


def plot_heatmap(heatmap_df: pd.DataFrame, output_path: Path, dpi: int) -> None:
    matrix = heatmap_df.pivot(
        index="instruction_type",
        columns="sdlc_stage",
        values="count",
    ).reindex(index=INSTRUCTION_TYPE_LABELS, columns=SDLC_STAGE_LABELS, fill_value=0)
    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    sns.heatmap(matrix, annot=True, fmt=".0f", cmap="Blues", cbar=False, ax=ax)
    ax.set_title("Python All\nInstruction Type x SDLC Stage (Retained Docs)")
    ax.set_xlabel("SDLC stage")
    ax.set_ylabel("Instruction type")
    ax.tick_params(axis="x", rotation=22)
    savefig(fig, str(output_path), dpi)


def write_analysis_report(
    out_dir: Path,
    summary_df: pd.DataFrame,
    structural_df: pd.DataFrame,
    sdlc_df: pd.DataFrame,
    heatmap_df: pd.DataFrame,
    both_file: str,
) -> Path:
    python_all_structural = (
        structural_df[structural_df["dataset"] == "Python All"]
        .sort_values("pct_docs", ascending=False)
        .reset_index(drop=True)
    )
    python_all_sdlc = (
        sdlc_df[sdlc_df["dataset"] == "Python All"]
        .sort_values("pct_docs", ascending=False)
        .reset_index(drop=True)
    )
    summary_all = summary_df[summary_df["dataset"] == "Python All"].iloc[0]
    strongest_instruction = python_all_structural.iloc[0]
    second_instruction = python_all_structural.iloc[1]
    strongest_stage = python_all_sdlc.iloc[0]
    second_stage = python_all_sdlc.iloc[1]
    heatmap_top = heatmap_df.sort_values("count", ascending=False).head(8)

    lines = [
        "# RQ3 Python All Analysis",
        "",
        f"- Selected `Both` source: `{both_file}`",
        f"- Combined dataset: `{int(summary_all['total_documents'])}` docs",
        f"- Retained after filtering: `{int(summary_all['retained_documents'])}` docs ({summary_all['retained_pct']:.2f}%)",
        f"- Filtered out: `{int(summary_all['filtered_documents'])}` docs ({summary_all['filtered_pct']:.2f}%)",
        f"- Filter source counts: `{summary_all['filter_source_document_counts']}`",
        "",
        "## Structural Patterns",
        f"- The dominant structural pattern in `Python All` is `{strongest_instruction['label']}` "
        f"({strongest_instruction['count']} docs, {strongest_instruction['pct_docs']:.2f}% of retained docs).",
        f"- The second strongest is `{second_instruction['label']}` "
        f"({second_instruction['count']} docs, {second_instruction['pct_docs']:.2f}%).",
        "- `reference` remains common, while `negative-examples` is comparatively rare.",
        "",
        "## Software Engineering Tasks",
        f"- The most common SDLC task family in `Python All` is `{strongest_stage['label']}` "
        f"({strongest_stage['count']} docs, {strongest_stage['pct_docs']:.2f}% of retained docs).",
        f"- The second most common is `{second_stage['label']}` "
        f"({second_stage['count']} docs, {second_stage['pct_docs']:.2f}%).",
        "- `Requirements` is the least represented stage in the combined Python dataset.",
        "",
        "## Cross-Source Notes",
        *[
            f"- `{row['dataset']}`: {int(row['retained_documents'])} retained / "
            f"{int(row['filtered_documents'])} filtered ({row['filtered_pct']:.2f}% filtered)."
            for _, row in summary_df.iterrows()
        ],
        "",
        "Most frequent instruction-type x SDLC-stage pairings in `Python All`:",
        *[
            f"- `{row['instruction_type']}` x `{row['sdlc_stage']}`: {int(row['count'])} docs"
            for _, row in heatmap_top.iterrows()
            if row["count"] > 0
        ],
    ]

    output_path = out_dir / "rq3_python_all_analysis.md"
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate structural-pattern and SDLC-task analysis for the combined Python dataset."
    )
    parser.add_argument(
        "--processed-dir",
        default="outputs/rq3/results/processed",
        help="Directory containing processed RQ3 exports and processed statistics.",
    )
    parser.add_argument(
        "--a-file",
        default=DEFAULT_A_FILE,
        help="Processed Python A file.",
    )
    parser.add_argument(
        "--b-file",
        default=DEFAULT_B_FILE,
        help="Processed Python B file.",
    )
    parser.add_argument(
        "--both-file",
        default=DEFAULT_BOTH_FILE,
        help="Processed Python Both file selected for Python_All.",
    )
    parser.add_argument(
        "--all-file",
        default=DEFAULT_ALL_FILE,
        help="Processed combined Python_All file.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/rq3/analysis/python_all",
        help="Directory for Python-All-specific tables, figures, and analysis.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Figure DPI.",
    )
    parser.add_argument(
        "--fig-format",
        default="png",
        choices=["png", "pdf", "svg"],
        help="Figure output format.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    processed_dir = resolve_path(args.processed_dir)
    out_dir = resolve_path(args.out_dir)

    configure_logging(args.log_level)
    setup_style()

    file_names = [args.a_file, args.b_file, args.both_file, args.all_file]
    dataset_map = load_dataset_stats(processed_dir, file_names)

    summary_df = build_summary_table(dataset_map)
    structural_df = build_distribution_table(
        dataset_map,
        "instruction_type_distribution_retained",
        INSTRUCTION_TYPE_LABELS,
    )
    sdlc_df = build_distribution_table(
        dataset_map,
        "sdlc_stage_distribution_retained",
        SDLC_STAGE_LABELS,
    )
    filter_df = build_filter_source_table(dataset_map)
    heatmap_df = build_python_all_heatmap_table(dataset_map)

    write_dataframe(summary_df, str(out_dir / "table_rq3_python_all_source_summary.csv"))
    write_dataframe(structural_df, str(out_dir / "table_rq3_python_all_structural_patterns.csv"))
    write_dataframe(sdlc_df, str(out_dir / "table_rq3_python_all_sdlc_tasks.csv"))
    write_dataframe(heatmap_df, str(out_dir / "table_rq3_python_all_instruction_stage_matrix.csv"))

    plot_grouped_percent_bars(
        structural_df,
        title="Python Dataset Sources\nStructural Patterns in SKILL.md Files (Retained Docs)",
        output_path=out_dir / f"fig_rq3_python_all_structural_patterns_comparison.{args.fig_format}",
        dpi=args.dpi,
    )
    plot_grouped_percent_bars(
        sdlc_df,
        title="Python Dataset Sources\nSoftware Engineering Task Types in SKILL.md Files (Retained Docs)",
        output_path=out_dir / f"fig_rq3_python_all_sdlc_tasks_comparison.{args.fig_format}",
        dpi=args.dpi,
    )
    plot_python_all_focus(
        structural_df,
        title="Python All\nStructural Patterns in SKILL.md Files",
        color="#42A5F5",
        output_path=out_dir / f"fig_rq3_python_all_structural_patterns.{args.fig_format}",
        dpi=args.dpi,
    )
    plot_python_all_focus(
        sdlc_df,
        title="Python All\nSoftware Engineering Task Types in SKILL.md Files",
        color="#66BB6A",
        output_path=out_dir / f"fig_rq3_python_all_sdlc_tasks.{args.fig_format}",
        dpi=args.dpi,
    )
    plot_retained_vs_filtered(
        summary_df,
        out_dir / f"fig_rq3_python_all_retained_vs_filtered.{args.fig_format}",
        args.dpi,
    )
    plot_filter_sources(
        filter_df,
        out_dir / f"fig_rq3_python_all_filter_sources.{args.fig_format}",
        args.dpi,
    )
    plot_heatmap(
        heatmap_df,
        out_dir / f"fig_rq3_python_all_instruction_stage_heatmap.{args.fig_format}",
        args.dpi,
    )

    report_path = write_analysis_report(
        out_dir,
        summary_df,
        structural_df,
        sdlc_df,
        heatmap_df,
        args.both_file,
    )
    log.info("Wrote analysis report: %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
