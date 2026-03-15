from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import (
    PALETTE_ACF,
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

ACF_COLUMNS = {
    "has_CLAUDE": "CLAUDE.md",
    "has_AGENTS": "AGENTS.md",
    "has_COPILOT": "copilot-instructions.md",
}


def build_table(scan_df: pd.DataFrame) -> pd.DataFrame | None:
    present = [column for column in ACF_COLUMNS if column in scan_df.columns]
    if not present:
        log.warning("ACF columns not present in scan CSV; skipping Section 4.")
        return None

    found_df = scan_df[scan_df["found"]].copy()
    if found_df.empty:
        log.warning("No found repos; skipping ACF analysis.")
        return None

    for column in present:
        found_df[column] = pd.to_numeric(found_df[column], errors="coerce").fillna(0).astype(int)

    rows: list[dict[str, object]] = []
    for column, label in ACF_COLUMNS.items():
        if column not in found_df.columns:
            continue
        count = int(found_df[column].sum())
        rows.append(
            {
                "artifact": label,
                "count": count,
                "pct_of_skill_md_repos": round(100.0 * count / len(found_df), 1),
            }
        )

    if len(present) >= 2:
        for index, first in enumerate(present):
            for second in present[index + 1 :]:
                count = int((found_df[first] & found_df[second]).sum())
                rows.append(
                    {
                        "artifact": f"{ACF_COLUMNS[first]} + {ACF_COLUMNS[second]}",
                        "count": count,
                        "pct_of_skill_md_repos": round(100.0 * count / len(found_df), 1),
                    }
                )
    if len(present) == 3:
        count = int((found_df[present[0]] & found_df[present[1]] & found_df[present[2]]).sum())
        rows.append({"artifact": "All three", "count": count, "pct_of_skill_md_repos": round(100.0 * count / len(found_df), 1)})

    return pd.DataFrame(rows)


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    table = build_table(scan_df)
    if table is None or table.empty:
        return None

    write_dataframe(table, str(Path(out_dir) / "table4_acf_cooccurrence.csv"))

    single_rows = [row for row in table.to_dict("records") if "+" not in row["artifact"] and row["artifact"] != "All three"]
    labels = [row["artifact"] for row in single_rows]
    counts = [row["count"] for row in single_rows]
    total_found = int(scan_df["found"].sum())
    not_counts = [total_found - count for count in counts]

    fig, ax = plt.subplots(figsize=(7, 5))
    x = np.arange(len(labels))
    bars = ax.bar(x, counts, 0.5, label="Has artifact", color=PALETTE_ACF[: len(labels)], edgecolor="white")
    ax.bar(x, not_counts, 0.5, bottom=counts, label="No artifact", color=PALETTE_NOT_FOUND, edgecolor="white")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("Repository count")
    ax.set_title("Agent-Facing Artifact Co-occurrence\namong SKILL.md Repositories")
    ax.legend(loc="upper right")

    for bar, count in zip(bars, counts):
        if count > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() / 2, str(count), ha="center", va="center", fontsize=9, color="white", fontweight="bold")

    output_path = Path(out_dir) / f"fig3_acf_cooccurrence.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 3 and Table 4 for RQ1")
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
