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
    PALETTE_FOUND,
    PALETTE_NOT_FOUND,
    add_output_args,
    add_scan_input_args,
    configure_logging,
    load_scan_csv,
    resolve_filters,
    savefig,
    setup_style,
    write_dataframe,
)

log = logging.getLogger(__name__)


def normalize_license(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return "No license"
    mapping = {
        "MIT License": "MIT",
        "Apache License 2.0": "Apache-2.0",
        "GNU General Public License v3.0": "GPL-3.0",
        "GNU General Public License v2.0": "GPL-2.0",
        'BSD 3-Clause "New" or "Revised" License': "BSD-3-Clause",
        'BSD 2-Clause "Simplified" License': "BSD-2-Clause",
        "GNU Lesser General Public License v3.0": "LGPL-3.0",
        "GNU Affero General Public License v3.0": "AGPL-3.0",
    }
    return mapping.get(value.strip(), value.strip())


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    if "license" not in scan_df.columns:
        log.warning("No license column; skipping license analysis.")
        return None

    work = scan_df.copy()
    work["license_norm"] = work["license"].map(normalize_license)

    overall = work["license_norm"].value_counts()
    found = work[work["found"]]["license_norm"].value_counts()
    top_licenses = overall.head(10).index.tolist()
    table = pd.DataFrame(
        {
            "license": top_licenses,
            "all_repos": [int(overall.get(license_name, 0)) for license_name in top_licenses],
            "skill_md_repos": [int(found.get(license_name, 0)) for license_name in top_licenses],
        }
    )
    table["all_pct"] = (100.0 * table["all_repos"] / len(work)).round(1)
    n_found = int(work["found"].sum())
    table["skill_md_pct"] = (100.0 * table["skill_md_repos"] / n_found).round(1) if n_found else 0
    write_dataframe(table, str(Path(out_dir) / "table8_license_distribution.csv"))

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    x = np.arange(len(top_licenses))
    width = 0.35

    ax0 = axes[0]
    ax0.bar(x - width / 2, table["all_pct"], width, label="All repos", color=PALETTE_NOT_FOUND, edgecolor="gray")
    ax0.bar(x + width / 2, table["skill_md_pct"], width, label="SKILL.md repos", color=PALETTE_FOUND, edgecolor="white", alpha=0.85)
    ax0.set_xticks(x)
    ax0.set_xticklabels(top_licenses, rotation=40, ha="right", fontsize=9)
    ax0.set_ylabel("Percentage of repos (%)")
    ax0.set_title("License Distribution:\nAll Repos vs. SKILL.md Repos")
    ax0.legend()

    ax1 = axes[1]
    colors = sns.color_palette("Set3", n_colors=len(top_licenses))
    wedges, _, autotexts = ax1.pie(
        table["skill_md_repos"],
        labels=None,
        autopct="%1.1f%%",
        pctdistance=0.75,
        colors=colors,
        startangle=90,
        wedgeprops={"width": 0.55, "edgecolor": "white"},
    )
    for autotext in autotexts:
        autotext.set_fontsize(8)
    ax1.legend(wedges, top_licenses, loc="lower center", bbox_to_anchor=(0.5, -0.15), ncol=3, fontsize=8)
    ax1.set_title("License Breakdown\nfor SKILL.md Repositories")

    output_path = Path(out_dir) / f"fig9_license_distribution.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 9 and Table 8 for RQ1")
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
