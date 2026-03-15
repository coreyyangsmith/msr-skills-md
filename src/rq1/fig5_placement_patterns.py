from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import add_output_args, add_scan_input_args, configure_logging, load_scan_csv, resolve_filters, savefig, setup_style, write_dataframe

log = logging.getLogger(__name__)


def classify_placement(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        return "unknown"
    candidate = path.strip().lower().lstrip("/")
    if candidate == "skill.md":
        return "root"
    if candidate.startswith(".github/"):
        return ".github/ subtree"
    if re.match(r"^(skills?|claude-?skill|codex-?skill|skill-?set)/", candidate):
        return "skills/ subfolder"
    if re.match(r"^\.(cursor|codex|vscode|config)/", candidate):
        return ".cursor/.codex/config subtree"
    if re.match(r"^nanobot/", candidate):
        return "nanobot/ subtree"
    return "other subfolder"


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    found_df = scan_df[scan_df["found"]].copy()
    if found_df.empty or "match_path" not in found_df.columns:
        log.warning("No found repos or match_path missing; skipping placement analysis.")
        return None

    if "skill_paths" in found_df.columns:
        all_paths: list[str] = []
        for _, row in found_df.iterrows():
            raw_paths = str(row.get("skill_paths") or row.get("match_path") or "")
            for path in raw_paths.split(";"):
                path = path.strip()
                if path:
                    all_paths.append(path)
        paths = pd.Series(all_paths)
    else:
        paths = found_df["match_path"].dropna()

    placement = paths.map(classify_placement)
    counts = placement.value_counts()
    table = counts.reset_index()
    table.columns = ["placement", "count"]
    table["pct"] = (100.0 * table["count"] / table["count"].sum()).round(1)
    write_dataframe(table, str(Path(out_dir) / "table5_placement_patterns.csv"))

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    colors = sns.color_palette("Set2", n_colors=len(counts))

    ax0 = axes[0]
    wedges, _, autotexts = ax0.pie(
        counts.values,
        labels=None,
        autopct="%1.1f%%",
        pctdistance=0.75,
        colors=colors,
        startangle=90,
        wedgeprops={"width": 0.55, "edgecolor": "white", "linewidth": 1.5},
    )
    for autotext in autotexts:
        autotext.set_fontsize(9)
    ax0.legend(
        wedges,
        [f"{label} (n={count})" for label, count in zip(counts.index, counts.values)],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=2,
        fontsize=9,
    )
    ax0.set_title("SKILL.md Placement Location Distribution")

    ax1 = axes[1]
    ax1.barh(table["placement"][::-1], table["count"][::-1], color=colors[::-1], edgecolor="white")
    for index, (count, pct) in enumerate(zip(table["count"][::-1], table["pct"][::-1])):
        ax1.text(count + 0.2, index, f"{count} ({pct}%)", va="center", fontsize=9)
    ax1.set_xlabel("Number of SKILL.md instances")
    ax1.set_title("SKILL.md Placement (absolute counts)")
    ax1.set_xlim(right=table["count"].max() * 1.35)

    output_path = Path(out_dir) / f"fig5_placement_patterns.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 5 and Table 5 for RQ1")
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
