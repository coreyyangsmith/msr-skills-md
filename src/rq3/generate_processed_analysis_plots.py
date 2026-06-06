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
import numpy as np
import pandas as pd
import seaborn as sns

from rq1.common import configure_logging, savefig, setup_style, write_dataframe
from rq3.build_python_all_dataset import language_defaults, language_slug
from rq3.label_processing import INSTRUCTION_TYPE_LABELS, SDLC_STAGE_LABELS

log = logging.getLogger(__name__)


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def compact_dataset_name(file_name: str) -> str:
    stem = Path(file_name).stem
    parts = stem.split("_")
    if len(parts) >= 6:
        return f"{parts[1]} {parts[0]} {parts[4]} {parts[5]}"
    return stem


def load_statistics(processed_dir: Path) -> tuple[dict[str, dict], pd.DataFrame]:
    stats_path = processed_dir / "processed_label_statistics.json"
    data = load_json(stats_path)
    dataset_rows = []
    dataset_map: dict[str, dict] = {}

    for item in data.get("datasets", []):
        dataset_map[item["file"]] = item
        dataset_rows.append(
            {
                "file": item["file"],
                "label": compact_dataset_name(item["file"]),
                "dataset_root": item.get("dataset_root"),
                "total_documents": item.get("total_documents", 0),
                "retained_documents": item.get("retained_documents", 0),
                "filtered_documents": item.get("filtered_documents", 0),
                "filtered_pct": item.get("filtered_pct", 0.0),
                "retained_pct": item.get("retained_pct", 0.0),
            }
        )

    return dataset_map, pd.DataFrame(dataset_rows)


def load_kappa_tables(processed_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    pair_rows: list[dict[str, object]] = []
    label_rows: list[dict[str, object]] = []

    for path in sorted(processed_dir.glob("kappa_*.json")):
        data = load_json(path)
        file1 = Path(data["file1"]).name
        file2 = Path(data["file2"]).name
        kappas = data.get("per_label_kappa", {})
        values = [entry["kappa"] for entry in kappas.values() if entry["kappa"] is not None]
        pair_rows.append(
            {
                "pair_file": path.name,
                "pair_label": f"{compact_dataset_name(file1)} vs {compact_dataset_name(file2)}",
                "file1": file1,
                "file2": file2,
                "common_docs": data.get("common_docs", 0),
                "avg_kappa": round(sum(values) / len(values), 4) if values else np.nan,
                "min_kappa": min(values) if values else np.nan,
                "label_count": len(values),
            }
        )
        for label, entry in sorted(kappas.items()):
            label_rows.append(
                {
                    "pair_file": path.name,
                    "pair_label": f"{compact_dataset_name(file1)} vs {compact_dataset_name(file2)}",
                    "file1": file1,
                    "file2": file2,
                    "label": label,
                    "kappa": entry.get("kappa"),
                    "observed_agreement": entry.get("observed_agreement"),
                    "support_r1": entry.get("support_r1"),
                    "support_r2": entry.get("support_r2"),
                    "n_docs": entry.get("n_docs"),
                }
            )

    return pd.DataFrame(pair_rows), pd.DataFrame(label_rows)


def language_file_tokens(language: str) -> tuple[str, ...]:
    defaults = language_defaults(language)
    if defaults.language == "Python":
        return ("_Python", "Python_All")
    if defaults.language == "TypeScript":
        return ("_TypeScript", "_TS", "TypeScript_All")
    return (f"_{defaults.language}", defaults.root_name)


def both_pair_tokens(language: str) -> tuple[str, ...]:
    defaults = language_defaults(language)
    if defaults.language == "Python":
        return ("Both_Python",)
    if defaults.language == "TypeScript":
        return ("Both_TypeScript", "Both_TS")
    return (f"Both_{defaults.language}",)


def _contains_any(series: pd.Series, tokens: tuple[str, ...]) -> pd.Series:
    mask = pd.Series(False, index=series.index)
    for token in tokens:
        mask = mask | series.str.contains(token, na=False, regex=False)
    return mask


def select_language_both_pairs(pair_df: pd.DataFrame, language: str) -> pd.DataFrame:
    tokens = both_pair_tokens(language)
    mask = _contains_any(pair_df["file1"], tokens) & _contains_any(pair_df["file2"], tokens)
    return pair_df.loc[mask].sort_values("pair_file").reset_index(drop=True)


def filter_language_datasets(dataset_df: pd.DataFrame, language: str) -> pd.DataFrame:
    tokens = language_file_tokens(language)
    return dataset_df.loc[_contains_any(dataset_df["file"], tokens)].reset_index(drop=True)


def build_distribution_table(
    dataset_map: dict[str, dict],
    file_names: list[str],
    key: str,
    label_order: tuple[str, ...] | list[str],
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for file_name in file_names:
        stats = dataset_map[file_name]
        distribution = stats.get(key, {})
        for label in label_order:
            entry = distribution.get(label, {})
            rows.append(
                {
                    "file": file_name,
                    "dataset": compact_dataset_name(file_name),
                    "label": label,
                    "count": entry.get("count", 0),
                    "pct_docs": entry.get("pct_docs", 0.0),
                }
            )
    return pd.DataFrame(rows)


def build_filter_source_table(dataset_map: dict[str, dict], file_names: list[str]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for file_name in file_names:
        stats = dataset_map[file_name]
        for label, count in stats.get("filter_source_document_counts", {}).items():
            rows.append(
                {
                    "file": file_name,
                    "dataset": compact_dataset_name(file_name),
                    "filter_source": label,
                    "count": count,
                }
            )
    return pd.DataFrame(rows)


def build_heatmap_matrix(stats: dict) -> pd.DataFrame:
    matrix = stats.get("instruction_x_sdlc_stage_retained", {})
    frame = pd.DataFrame(matrix).T if matrix else pd.DataFrame(index=INSTRUCTION_TYPE_LABELS)
    if frame.empty:
        frame = pd.DataFrame(0, index=INSTRUCTION_TYPE_LABELS, columns=SDLC_STAGE_LABELS)
    frame = frame.reindex(index=INSTRUCTION_TYPE_LABELS, columns=SDLC_STAGE_LABELS).fillna(0)
    return frame.astype(int)


def plot_latest_kappa(
    latest_labels: pd.DataFrame,
    out_dir: Path,
    fig_format: str,
    dpi: int,
    language: str,
    pair_slug: str,
) -> Path:
    plot_df = latest_labels.sort_values("kappa", ascending=True).copy()
    fig, ax = plt.subplots(figsize=(9, max(5.5, len(plot_df) * 0.45)))
    colors = sns.color_palette("RdYlGn", n_colors=len(plot_df))
    ax.barh(plot_df["label"], plot_df["kappa"], color=colors, edgecolor="white")
    ax.axvline(0.60, color="#666666", linestyle="--", linewidth=1, alpha=0.8)
    ax.set_xlim(-0.05, 1.05)
    ax.set_xlabel("Cohen's kappa")
    ax.set_title(f"RQ3 Processed Agreement\nLatest {language} Both Pair")
    for _, row in plot_df.iterrows():
        ax.text(
            row["kappa"] + 0.015,
            row["label"],
            f"{row['kappa']:.3f} ({int(row['support_r1'])}/{int(row['support_r2'])})",
            va="center",
            fontsize=9,
        )
    output_path = out_dir / f"fig_rq3_agreement_latest_{pair_slug}.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def plot_pair_comparison(
    compare_df: pd.DataFrame,
    out_dir: Path,
    fig_format: str,
    dpi: int,
    language: str,
    pair_slug: str,
) -> Path:
    pivot = compare_df.pivot(index="label", columns="pair_label", values="kappa").fillna(0.0)
    order = pivot.mean(axis=1).sort_values().index
    pivot = pivot.loc[order]
    fig, ax = plt.subplots(figsize=(11, max(5.5, len(pivot) * 0.5)))
    pivot.plot(kind="barh", ax=ax, width=0.8, color=sns.color_palette("Set2", n_colors=len(pivot.columns)))
    ax.set_xlim(-0.05, 1.05)
    ax.set_xlabel("Cohen's kappa")
    ax.set_ylabel("")
    ax.set_title(f"RQ3 Processed Agreement\n{language} Both Pair Comparison")
    ax.legend(title="Pair", fontsize=9, title_fontsize=10, loc="lower right")
    output_path = out_dir / f"fig_rq3_agreement_{pair_slug}_pairs.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def plot_filtered_vs_retained(
    dataset_df: pd.DataFrame,
    out_dir: Path,
    fig_format: str,
    dpi: int,
    language_slug_value: str,
) -> Path:
    plot_df = dataset_df.sort_values("filtered_pct", ascending=True).copy()
    fig, ax = plt.subplots(figsize=(10, max(5.5, len(plot_df) * 0.55)))
    ax.barh(plot_df["label"], plot_df["retained_documents"], color="#4CAF50", label="Retained")
    ax.barh(
        plot_df["label"],
        plot_df["filtered_documents"],
        left=plot_df["retained_documents"],
        color="#FF8A65",
        label="Filtered",
    )
    ax.set_xlabel("Document count")
    ax.set_ylabel("")
    ax.set_title("RQ3 Processed Datasets\nRetained vs Filtered Documents")
    ax.legend(loc="lower right")
    for _, row in plot_df.iterrows():
        total = int(row["total_documents"])
        ax.text(
            total + 1,
            row["label"],
            f"{row['filtered_pct']:.1f}% filtered",
            va="center",
            fontsize=9,
        )
    output_path = out_dir / f"fig_rq3_retained_vs_filtered_{language_slug_value}.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def plot_filter_source_breakdown(
    filter_df: pd.DataFrame,
    out_dir: Path,
    fig_format: str,
    dpi: int,
    language: str,
    pair_slug: str,
) -> Path:
    pivot = filter_df.pivot(index="dataset", columns="filter_source", values="count").fillna(0)
    order = [name for name in pivot.index]
    pivot = pivot.loc[order]
    fig, ax = plt.subplots(figsize=(8, 5))
    pivot.plot(
        kind="bar",
        stacked=True,
        ax=ax,
        color=["#5C6BC0", "#FFB74D", "#EF5350"],
        edgecolor="white",
    )
    ax.set_ylabel("Filtered document count")
    ax.set_xlabel("")
    ax.set_title(f"Latest {language} Both Pair\nFilter Source Breakdown")
    ax.legend(title="Original filter source", fontsize=9, title_fontsize=10)
    ax.tick_params(axis="x", rotation=12)
    output_path = out_dir / f"fig_rq3_filter_sources_latest_{pair_slug}.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def plot_distribution_comparison(
    df: pd.DataFrame,
    title: str,
    ylabel: str,
    output_name: str,
    out_dir: Path,
    fig_format: str,
    dpi: int,
) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.5))
    sns.barplot(data=df, x="label", y="pct_docs", hue="dataset", ax=ax)
    ax.set_title(title)
    ax.set_xlabel("")
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=20)
    ax.legend(title="Dataset", fontsize=9, title_fontsize=10)
    output_path = out_dir / f"{output_name}.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def plot_heatmaps(
    left_stats: dict,
    right_stats: dict,
    out_dir: Path,
    fig_format: str,
    dpi: int,
    language: str,
    pair_slug: str,
) -> Path:
    left = build_heatmap_matrix(left_stats)
    right = build_heatmap_matrix(right_stats)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.5), sharey=True)
    vmax = max(left.to_numpy().max(), right.to_numpy().max(), 1)

    sns.heatmap(left, annot=True, fmt="d", cmap="Blues", cbar=False, ax=axes[0], vmin=0, vmax=vmax)
    sns.heatmap(right, annot=True, fmt="d", cmap="Blues", cbar=False, ax=axes[1], vmin=0, vmax=vmax)
    axes[0].set_title(compact_dataset_name(left_stats["file"]))
    axes[1].set_title(compact_dataset_name(right_stats["file"]))
    for ax in axes:
        ax.set_xlabel("SDLC stage")
        ax.set_ylabel("Instruction type")
        ax.tick_params(axis="x", rotation=20)
    fig.suptitle(f"Latest {language} Both Pair\nInstruction Type x SDLC Stage (Retained Docs)")

    output_path = out_dir / f"fig_rq3_instruction_stage_heatmap_latest_{pair_slug}.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def write_analysis_report(
    out_dir: Path,
    pair_df: pd.DataFrame,
    latest_pair: pd.Series,
    latest_labels: pd.DataFrame,
    dataset_df: pd.DataFrame,
    latest_left_stats: dict,
    latest_right_stats: dict,
    language: str,
    pair_slug: str,
) -> Path:
    older_pair = pair_df.iloc[0] if len(pair_df) > 1 else None
    low_labels = latest_labels.sort_values("kappa").head(5)
    high_labels = latest_labels.sort_values("kappa", ascending=False).head(5)
    filtered_sorted = dataset_df.sort_values("filtered_pct", ascending=False)

    lines = [
        f"# RQ3 Processed {language} Label Analysis",
        "",
        "## Agreement",
        f"- Latest {language} Both pair: `{latest_pair['pair_label']}`",
        f"- Average kappa across collapsed labels: `{latest_pair['avg_kappa']:.4f}`",
    ]
    if older_pair is not None:
        delta = latest_pair["avg_kappa"] - older_pair["avg_kappa"]
        lines.append(
            f"- Change vs earliest {language} Both pair: `{delta:+.4f}` "
            f"({older_pair['avg_kappa']:.4f} -> {latest_pair['avg_kappa']:.4f})"
        )
    lines.extend(
        [
            "",
            "Lowest-agreement labels in the latest pair:",
            *[
                f"- `{row['label']}`: kappa `{row['kappa']:.4f}` "
                f"(supports `{int(row['support_r1'])}` vs `{int(row['support_r2'])}`)"
                for _, row in low_labels.iterrows()
            ],
            "",
            "Highest-agreement labels in the latest pair:",
            *[
                f"- `{row['label']}`: kappa `{row['kappa']:.4f}`"
                for _, row in high_labels.iterrows()
            ],
            "",
            "## Filtering",
            *[
                f"- `{row['label']}`: `{row['filtered_pct']:.2f}%` filtered "
                f"({int(row['filtered_documents'])}/{int(row['total_documents'])} docs)"
                for _, row in filtered_sorted.iterrows()
            ],
            "",
            f"Latest {language} Both pair filter-source counts:",
            f"- `{compact_dataset_name(latest_left_stats['file'])}`: `{latest_left_stats['filter_source_document_counts']}`",
            f"- `{compact_dataset_name(latest_right_stats['file'])}`: `{latest_right_stats['filter_source_document_counts']}`",
            "",
            "## Latest Pair Patterns",
            f"- `{compact_dataset_name(latest_left_stats['file'])}` retained docs are led by "
            f"`{', '.join(list(latest_left_stats['label_distribution_retained'])[:5])}`.",
            f"- `{compact_dataset_name(latest_right_stats['file'])}` retained docs are led by "
            f"`{', '.join(list(latest_right_stats['label_distribution_retained'])[:5])}`.",
            f"- Strongest SDLC stage in `{compact_dataset_name(latest_left_stats['file'])}`: "
            f"`{max(latest_left_stats['sdlc_stage_distribution_retained'].items(), key=lambda kv: kv[1]['count'])[0]}`.",
            f"- Strongest SDLC stage in `{compact_dataset_name(latest_right_stats['file'])}`: "
            f"`{max(latest_right_stats['sdlc_stage_distribution_retained'].items(), key=lambda kv: kv[1]['count'])[0]}`.",
        ]
    )

    output_path = out_dir / f"rq3_processed_analysis_{pair_slug}.md"
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate plots and a short analysis brief for processed RQ3 outputs."
    )
    parser.add_argument(
        "--language",
        default="Python",
        help="Language-specific Both pair to analyze. TypeScript accepts both _TypeScript and _TS filename suffixes.",
    )
    parser.add_argument(
        "--processed-dir",
        default="outputs/rq3/results/processed",
        help="Directory containing processed RQ3 results.",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/rq3/analysis",
        help="Directory for plots and analysis artifacts.",
    )
    parser.add_argument(
        "--fig-format",
        default="png",
        choices=["png", "pdf", "svg"],
        help="Figure output format.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Figure DPI.",
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
    defaults = language_defaults(args.language)
    pair_slug = f"{language_slug(defaults.language)}_both"

    configure_logging(args.log_level)
    setup_style()

    dataset_map, dataset_df = load_statistics(processed_dir)
    pair_df, label_df = load_kappa_tables(processed_dir)
    if dataset_df.empty or pair_df.empty or label_df.empty:
        raise SystemExit("Processed statistics or kappa files are missing or empty.")

    language_pair_df = select_language_both_pairs(pair_df, defaults.language)
    if language_pair_df.empty:
        raise SystemExit(f"No processed {defaults.language} Both kappa files were found.")

    latest_pair = language_pair_df.iloc[-1]
    latest_pair_file = latest_pair["pair_file"]
    latest_labels = label_df[label_df["pair_file"] == latest_pair_file].copy()
    compare_labels = label_df[label_df["pair_file"].isin(language_pair_df["pair_file"])].copy()
    language_dataset_df = filter_language_datasets(dataset_df, defaults.language)

    latest_file_names = [latest_pair["file1"], latest_pair["file2"]]
    latest_left_stats = dataset_map[latest_file_names[0]]
    latest_right_stats = dataset_map[latest_file_names[1]]

    instruction_df = build_distribution_table(
        dataset_map,
        latest_file_names,
        "instruction_type_distribution_retained",
        INSTRUCTION_TYPE_LABELS,
    )
    sdlc_df = build_distribution_table(
        dataset_map,
        latest_file_names,
        "sdlc_stage_distribution_retained",
        SDLC_STAGE_LABELS,
    )
    filter_df = build_filter_source_table(dataset_map, latest_file_names)

    write_dataframe(
        latest_labels.sort_values("kappa"),
        str(out_dir / f"table_rq3_latest_{pair_slug}_kappa.csv"),
    )
    write_dataframe(
        compare_labels.sort_values(["label", "pair_file"]),
        str(out_dir / f"table_rq3_{pair_slug}_pair_comparison.csv"),
    )
    write_dataframe(
        language_dataset_df.sort_values("filtered_pct", ascending=False),
        str(out_dir / f"table_rq3_{language_slug(defaults.language)}_dataset_filter_summary.csv"),
    )
    write_dataframe(
        instruction_df,
        str(out_dir / f"table_rq3_latest_{pair_slug}_instruction_distribution.csv"),
    )
    write_dataframe(
        sdlc_df,
        str(out_dir / f"table_rq3_latest_{pair_slug}_sdlc_distribution.csv"),
    )

    plot_latest_kappa(latest_labels, out_dir, args.fig_format, args.dpi, defaults.language, pair_slug)
    plot_pair_comparison(compare_labels, out_dir, args.fig_format, args.dpi, defaults.language, pair_slug)
    plot_filtered_vs_retained(language_dataset_df, out_dir, args.fig_format, args.dpi, language_slug(defaults.language))
    plot_filter_source_breakdown(filter_df, out_dir, args.fig_format, args.dpi, defaults.language, pair_slug)
    plot_distribution_comparison(
        instruction_df,
        f"Latest {defaults.language} Both Pair\nInstruction-Type Distribution (Retained Docs)",
        "% of retained docs",
        f"fig_rq3_instruction_distribution_latest_{pair_slug}",
        out_dir,
        args.fig_format,
        args.dpi,
    )
    plot_distribution_comparison(
        sdlc_df,
        f"Latest {defaults.language} Both Pair\nSDLC Stage Distribution (Retained Docs)",
        "% of retained docs",
        f"fig_rq3_sdlc_stage_distribution_latest_{pair_slug}",
        out_dir,
        args.fig_format,
        args.dpi,
    )
    plot_heatmaps(latest_left_stats, latest_right_stats, out_dir, args.fig_format, args.dpi, defaults.language, pair_slug)
    report_path = write_analysis_report(
        out_dir,
        language_pair_df,
        latest_pair,
        latest_labels,
        language_dataset_df,
        latest_left_stats,
        latest_right_stats,
        defaults.language,
        pair_slug,
    )
    log.info("Wrote analysis report: %s", report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
