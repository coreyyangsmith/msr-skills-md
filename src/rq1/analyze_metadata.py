#!/usr/bin/env python3
"""Wrapper entrypoint for the split RQ1 scan-based analyses."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1 import (
    acf_environment_analysis,
    fig10_language_ecosystem,
    fig11_project_maturity,
    fig12_presence_by_contributor_count,
    fig13_presence_by_project_size,
    fig14_presence_by_project_age,
    fig21_scale_visibility_collaboration_age,
    fig22_acf_intersections_language_heatmap,
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
    table_top1000_repos_global,
)
from rq1.common import (
    add_instances_input_args,
    add_output_args,
    add_screening_input_args,
    add_scan_input_args,
    aggregate_instances_to_repo,
    apply_screening_decisions,
    configure_logging,
    load_instances_csv,
    load_scan_csv,
    merge_repo_metadata,
    resolve_filters,
    resolve_screening_decisions,
    setup_style,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="RQ1 analysis: SKILL.md prevalence and adoption across open-source repos."
    )
    add_scan_input_args(parser)
    parser.add_argument(
        "--acf-scan-csv",
        default="",
        help=(
            "Optional scan CSV for ACF-specific figures/tables. Use this when the ACF "
            "enrichment is available as a SKILL.md-only file, while --scan-csv remains "
            "the full corpus for prevalence analyses."
        ),
    )
    add_instances_input_args(parser, required=True)
    add_screening_input_args(parser)
    add_output_args(parser)
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)
    setup_style()
    os.makedirs(args.out_dir, exist_ok=True)

    blacklist, filter_words = resolve_filters(args)
    scan_df = load_scan_csv(args.scan_csv, blacklist=blacklist, filter_words=filter_words)
    screening_decisions = resolve_screening_decisions(args)
    scan_df = apply_screening_decisions(scan_df, screening_decisions, "scan CSV")

    acf_scan_df = scan_df
    if args.acf_scan_csv:
        acf_scan_df = load_scan_csv(args.acf_scan_csv, blacklist=blacklist, filter_words=filter_words)
        acf_scan_df = apply_screening_decisions(acf_scan_df, screening_decisions, "ACF scan CSV")

    raw_instances_df = load_instances_csv(args.instances_csv)
    if raw_instances_df is None:
        log.error("Instances CSV missing or unreadable: %s", args.instances_csv)
        return 2
    raw_instances_df = apply_screening_decisions(raw_instances_df, screening_decisions, "instances CSV")

    repo_instances_df = aggregate_instances_to_repo(raw_instances_df)
    repo_instances_df = merge_repo_metadata(repo_instances_df, scan_df)

    table1_dataset_summary.generate(scan_df, args.out_dir)
    fig1_prevalence_by_language.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig2_prevalence_by_size_stars.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig3_acf_cooccurrence.generate(acf_scan_df, args.out_dir, args.fig_format, args.dpi)
    fig4_acf_pairwise_heatmap.generate(acf_scan_df, args.out_dir, args.fig_format, args.dpi)
    acf_environment_analysis.generate(acf_scan_df, args.out_dir, args.fig_format, args.dpi)
    fig5_placement_patterns.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig6_temporal_trend.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig7_topic_analysis.generate(scan_df, args.out_dir, args.fig_format, args.dpi)

    fig8_skill_richness.generate(repo_instances_df, args.out_dir, args.fig_format, args.dpi)
    fig8b_stars_vs_skill_count.generate(repo_instances_df, args.out_dir, args.fig_format, args.dpi)
    table_top1000_repos_global.generate(repo_instances_df, args.out_dir)

    fig10_language_ecosystem.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig9_license_distribution.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig11_project_maturity.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig12_presence_by_contributor_count.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig13_presence_by_project_size.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig14_presence_by_project_age.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig21_scale_visibility_collaboration_age.generate(scan_df, args.out_dir, args.fig_format, args.dpi)
    fig22_acf_intersections_language_heatmap.generate(acf_scan_df, args.out_dir, args.fig_format, args.dpi)

    print(f"\nAll outputs written to: {os.path.abspath(args.out_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
