#!/usr/bin/env python3
"""Wrapper entrypoint for the split RQ1 scan-based analyses."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1 import (
    fig10_language_ecosystem,
    fig11_project_maturity,
    fig12_presence_by_contributor_count,
    fig13_presence_by_project_size,
    fig14_presence_by_project_age,
    fig1_prevalence_by_language,
    fig2_prevalence_by_size_stars,
    fig3_acf_cooccurrence,
    fig4_acf_pairwise_heatmap,
    fig5_placement_patterns,
    fig6_temporal_trend,
    fig7_topic_analysis,
    fig8_skill_richness,
    fig8b_stars_vs_skill_count,
    fig9_license_distribution,
    table1_dataset_summary,
)
from rq1.common import (
    add_instances_input_args,
    add_output_args,
    add_scan_input_args,
    aggregate_instances_to_repo,
    configure_logging,
    load_instances_csv,
    load_scan_csv,
    merge_repo_metadata,
    resolve_filters,
    setup_style,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RQ1 analysis: SKILL.md prevalence and adoption across open-source repos."
    )
    add_scan_input_args(parser)
    add_instances_input_args(parser, required=False)
    add_output_args(parser)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    setup_style()
    os.makedirs(args.out_dir, exist_ok=True)

    blacklist, filter_words = resolve_filters(args)
    scan_df = load_scan_csv(args.scan_csv, blacklist=blacklist, filter_words=filter_words)

    repo_instances_df = None
    if args.instances_csv:
        raw_instances_df = load_instances_csv(args.instances_csv, blacklist=blacklist, filter_words=filter_words)
        if raw_instances_df is not None:
            repo_instances_df = aggregate_instances_to_repo(raw_instances_df)
            repo_instances_df = merge_repo_metadata(repo_instances_df, scan_df)

    table1_dataset_summary.generate(scan_df, args.out_dir)
    fig1_prevalence_by_language.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig2_prevalence_by_size_stars.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig3_acf_cooccurrence.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig4_acf_pairwise_heatmap.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig5_placement_patterns.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig6_temporal_trend.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig7_topic_analysis.generate(scan_df, args.out_dir, args.fig_format, args.dpi)

    if repo_instances_df is not None:
        fig8_skill_richness.generate(repo_instances_df, args.out_dir, args.fig_format, args.dpi)
        fig8b_stars_vs_skill_count.generate(repo_instances_df, args.out_dir, args.fig_format, args.dpi)

    fig10_language_ecosystem.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig9_license_distribution.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig11_project_maturity.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig12_presence_by_contributor_count.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig13_presence_by_project_size.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig14_presence_by_project_age.generate(scan_df, args.out_dir, args.fig_format, args.dpi)

    print(f"\nAll outputs written to: {os.path.abspath(args.out_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
