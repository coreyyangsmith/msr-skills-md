from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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


def _parse_languages(value: str) -> dict[str, int]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        return json.loads(value.replace('""', '"'))
    except Exception:
        return {}


def generate(scan_df: pd.DataFrame, out_dir: str, fig_format: str, dpi: int) -> Path | None:
    found_df = scan_df[scan_df["found"]].copy()
    has_language_json = (
        "languages" in scan_df.columns
        and scan_df["languages"].notna().any()
        and scan_df["languages"].astype(str).str.strip().replace("", pd.NA).notna().any()
    )

    if has_language_json:
        def extract_language_bytes(df: pd.DataFrame) -> dict[str, int]:
            language_bytes: dict[str, int] = {}
            for value in df["languages"]:
                for language, byte_count in _parse_languages(value).items():
                    language_bytes[language] = language_bytes.get(language, 0) + int(byte_count or 0)
            return language_bytes

        all_language_bytes = extract_language_bytes(scan_df)
        found_language_bytes = extract_language_bytes(found_df)
        if not all_language_bytes:
            has_language_json = False

    if has_language_json:
        top_languages = sorted(all_language_bytes, key=all_language_bytes.get, reverse=True)[:15]
        table = pd.DataFrame(
            {
                "language": top_languages,
                "all_bytes": [all_language_bytes.get(language, 0) for language in top_languages],
                "found_bytes": [found_language_bytes.get(language, 0) for language in top_languages],
            }
        )
        table["found_share_pct"] = (100.0 * table["found_bytes"] / table["all_bytes"].replace(0, np.nan)).round(1)

        fig, ax = plt.subplots(figsize=(10, 6))
        x = np.arange(len(top_languages))
        width = 0.4
        ax.bar(x - width / 2, table["all_bytes"] / 1e6, width, label="All repos (MB)", color=PALETTE_NOT_FOUND, edgecolor="gray")
        ax.bar(x + width / 2, table["found_bytes"] / 1e6, width, label="SKILL.md repos (MB)", color=PALETTE_FOUND, edgecolor="white", alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(top_languages, rotation=40, ha="right")
        ax.set_ylabel("Code volume (MB)")
        ax.set_title("Language Ecosystem: Code Volume Distribution\n(All Repos vs. SKILL.md Repos)")
        ax.legend()
    else:
        language_col = "mainLanguage" if "mainLanguage" in scan_df.columns else None
        if language_col is None:
            log.warning("No languages or mainLanguage column; skipping ecosystem analysis.")
            return None

        all_counts = scan_df[language_col].fillna("(unknown)").value_counts()
        found_counts = found_df[language_col].fillna("(unknown)").value_counts()
        top_languages = all_counts.head(15).index.tolist()
        table = pd.DataFrame(
            {
                "language": top_languages,
                "all_repos": [int(all_counts.get(language, 0)) for language in top_languages],
                "found_repos": [int(found_counts.get(language, 0)) for language in top_languages],
            }
        )
        table["found_share_pct"] = (100.0 * table["found_repos"] / table["all_repos"].replace(0, np.nan)).round(1)

        fig, ax = plt.subplots(figsize=(10, 6))
        x = np.arange(len(top_languages))
        width = 0.4
        ax.bar(x - width / 2, table["all_repos"], width, label="All repos", color=PALETTE_NOT_FOUND, edgecolor="gray")
        ax.bar(x + width / 2, table["found_repos"], width, label="SKILL.md repos", color=PALETTE_FOUND, edgecolor="white", alpha=0.85)
        ax.set_xticks(x)
        ax.set_xticklabels(top_languages, rotation=40, ha="right")
        ax.set_ylabel("Repository count")
        ax.set_title("Language Ecosystem: Repository Count Distribution\n(All Repos vs. SKILL.md Repos)")
        ax.legend()

    write_dataframe(table, str(Path(out_dir) / "table9_language_ecosystem.csv"))
    output_path = Path(out_dir) / f"fig10_language_ecosystem.{fig_format}"
    savefig(fig, str(output_path), dpi)
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Fig 10 and Table 9 for RQ1")
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
