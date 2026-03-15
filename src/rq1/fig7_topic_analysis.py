from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import add_output_args, add_scan_input_args, configure_logging, load_scan_csv, resolve_filters, savefig, setup_style, write_dataframe

log = logging.getLogger(__name__)


def _parse_topics(value: str) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    return [topic.strip() for topic in value.split(";") if topic.strip()]


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    if "topics" not in scan_df.columns:
        log.warning("No topics column; skipping topic analysis.")
        return None

    all_topics: list[str] = []
    found_topics: list[str] = []
    for _, row in scan_df.iterrows():
        topics = _parse_topics(str(row.get("topics") or ""))
        all_topics.extend(topics)
        if row.get("found"):
            found_topics.extend(topics)

    if not all_topics:
        log.warning("No topic data found; skipping topic analysis.")
        return None

    all_counts = pd.Series(all_topics).value_counts()
    found_counts = pd.Series(found_topics).value_counts()
    table = pd.DataFrame({"topic": all_counts.index, "total_repos": all_counts.values})
    table["found_repos"] = table["topic"].map(found_counts).fillna(0).astype(int)
    table["found_rate_pct"] = 100.0 * table["found_repos"] / table["total_repos"].replace(0, pd.NA)
    overall_rate = 100.0 * int(scan_df["found"].sum()) / len(scan_df) if len(scan_df) else 0.0
    table["enrichment_ratio"] = table["found_rate_pct"] / overall_rate if overall_rate else pd.NA
    table = table.sort_values("enrichment_ratio", ascending=False)
    top20 = table[table["total_repos"] >= 2].head(20)
    write_dataframe(top20, str(Path(out_dir) / "table6_topic_enrichment.csv"))

    top_found = found_counts.head(20)
    if top_found.empty:
        log.warning("No found topics to plot; skipping topic figure.")
        return None

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    ax0 = axes[0]
    colors0 = sns.color_palette("Blues_r", n_colors=len(top_found))
    ax0.barh(top_found.index[::-1], top_found.values[::-1], color=colors0[::-1], edgecolor="white")
    ax0.set_xlabel("Frequency in SKILL.md repositories")
    ax0.set_title("Top Topics in SKILL.md Repositories")

    plot_enrich = top20[top20["enrichment_ratio"].notna()].head(15)
    ax1 = axes[1]
    colors1 = sns.color_palette("Oranges_r", n_colors=len(plot_enrich))
    ax1.barh(plot_enrich["topic"][::-1], plot_enrich["enrichment_ratio"][::-1], color=colors1[::-1], edgecolor="white")
    ax1.axvline(1.0, color="gray", linestyle="--", linewidth=1, label="Baseline rate")
    ax1.set_xlabel("Enrichment ratio (vs. overall prevalence)")
    ax1.set_title("Most Enriched Topics in SKILL.md Repos\n(min. 2 total repos)")
    ax1.legend()

    output_path = Path(out_dir) / f"fig7_topic_analysis.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 7 and Table 6 for RQ1")
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
