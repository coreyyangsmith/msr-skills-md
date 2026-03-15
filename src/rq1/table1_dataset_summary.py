from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import add_output_args, add_scan_input_args, configure_logging, load_scan_csv, resolve_filters, write_dataframe

log = logging.getLogger(__name__)


def generate(scan_df, out_dir: str) -> Path:
    total = len(scan_df)
    found_mask = scan_df["found"]
    n_found = int(found_mask.sum())
    n_not_found = int((~found_mask).sum())

    error_cols = scan_df.get("error_type")
    if error_cols is None:
        n_errors = 0
        n_filtered = 0
    else:
        n_errors = int(
            error_cols.isin(["rate_limited", "network", "auth", "invalid_repo", "not_found", "other"]).sum()
        )
        n_filtered = int((error_cols == "filtered").sum())

    prevalence = 100.0 * n_found / total if total else 0.0
    summary = [
        ("Total repos scanned", total),
        ("SKILL.md found", n_found),
        ("SKILL.md not found", n_not_found),
        ("API errors", n_errors),
        ("Filtered out", n_filtered),
        ("Prevalence rate (%)", f"{prevalence:.2f}"),
    ]
    df = pd.DataFrame(summary, columns=["Metric", "Value"])
    output_path = Path(out_dir) / "table1_dataset_summary.csv"
    write_dataframe(df, str(output_path))
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Table 1 dataset summary for RQ1")
    add_scan_input_args(parser)
    add_output_args(parser)
    args = parser.parse_args(argv)

    configure_logging(args.log_level)
    blacklist, filter_words = resolve_filters(args)
    scan_df = load_scan_csv(args.scan_csv, blacklist=blacklist, filter_words=filter_words)
    generate(scan_df, args.out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
