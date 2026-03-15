#!/usr/bin/env python3
"""Populate contributor counts for a scan CSV using the GitHub contributors API."""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import pandas as pd

from github_client import GitHubClient, TokenPool, load_tokens_from_env

log = logging.getLogger(__name__)

PAGE_RE = re.compile(r"[?&]page=(\d+)")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich a scan CSV with contributor counts")
    parser.add_argument("--scan-csv", required=True, help="Input scan CSV")
    parser.add_argument("--out-csv", default="", help="Output CSV path (defaults to <scan>_with_contributors.csv)")
    parser.add_argument("--resume", action="store_true", help="Reuse any contributor counts already present in out-csv")
    parser.add_argument("--concurrency", type=int, default=4, help="Worker threads")
    parser.add_argument("--max-repos", type=int, default=0, help="Limit rows processed (0 means no limit)")
    parser.add_argument("--github-token", default="", help="Single GitHub token (overrides env).")
    parser.add_argument("--github-tokens", default="", help="Comma-separated GitHub tokens (overrides env).")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args(argv)


def resolve_tokens(args: argparse.Namespace) -> list[str]:
    raw_tokens = args.github_tokens.strip() or args.github_token.strip()
    if raw_tokens:
        return [token.strip() for token in raw_tokens.split(",") if token.strip()]
    return load_tokens_from_env()


def default_output_path(scan_csv: str) -> str:
    scan_path = Path(scan_csv)
    return str(scan_path.with_name(f"{scan_path.stem}_with_contributors{scan_path.suffix}"))


def parse_last_page(link_header: str) -> Optional[int]:
    if not link_header:
        return None
    pages = [int(match.group(1)) for match in PAGE_RE.finditer(link_header)]
    return max(pages) if pages else None


def fetch_contributor_count(gh: GitHubClient, repo: str) -> tuple[Optional[int], str]:
    owner, name = repo.split("/", 1)
    status, body, headers, err = gh.request_json_with_headers(
        "GET",
        f"/repos/{owner}/{name}/contributors",
        params={"per_page": 1, "anon": 1},
    )

    if status == 204:
        return (0, "")
    if status != 200:
        return (None, f"http_{status}: {err}")
    if not isinstance(body, list):
        return (None, "unexpected_response")

    last_page = parse_last_page(headers.get("Link", ""))
    if last_page is not None:
        return (last_page, "")
    return (len(body), "")


def merge_resume_data(base_df: pd.DataFrame, out_csv: str) -> pd.DataFrame:
    if not os.path.exists(out_csv):
        return base_df

    previous_df = pd.read_csv(out_csv, low_memory=False)
    if "repo" not in previous_df.columns or "contributors" not in previous_df.columns:
        return base_df

    previous = (
        previous_df[["repo", "contributors"]]
        .dropna(subset=["repo"])
        .drop_duplicates(subset=["repo"], keep="last")
        .set_index("repo")["contributors"]
    )
    missing = base_df["contributors"].isna()
    base_df.loc[missing, "contributors"] = base_df.loc[missing, "repo"].map(previous)
    return base_df


def write_csv_atomically(df: pd.DataFrame, out_csv: str) -> None:
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=out_path.parent, suffix=out_path.suffix, encoding="utf-8", newline="") as handle:
        temp_path = Path(handle.name)
        df.to_csv(handle.name, index=False)
    os.replace(temp_path, out_path)


def prepare_working_dataframe(scan_csv: str, out_csv: str, resume: bool) -> pd.DataFrame:
    df = pd.read_csv(scan_csv, low_memory=False)
    if "repo" not in df.columns:
        raise ValueError("scan CSV is missing the 'repo' column")
    if "contributors" not in df.columns:
        df["contributors"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    else:
        df["contributors"] = pd.to_numeric(df["contributors"], errors="coerce").astype("Int64")

    if resume:
        df = merge_resume_data(df, out_csv)
        df["contributors"] = pd.to_numeric(df["contributors"], errors="coerce").astype("Int64")

    return df


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    out_csv = args.out_csv or default_output_path(args.scan_csv)
    df = prepare_working_dataframe(args.scan_csv, out_csv, args.resume)

    pending = df["repo"].notna() & df["contributors"].isna()
    pending_indices = df.index[pending].tolist()
    if args.max_repos and args.max_repos > 0:
        pending_indices = pending_indices[: args.max_repos]

    if not pending_indices:
        log.info("No repositories need contributor enrichment.")
        write_csv_atomically(df, out_csv)
        return 0

    tokens = resolve_tokens(args)
    if not tokens:
        log.warning(
            "No GitHub token detected. Unauthenticated core rate limits are low. "
            "Set GH_TOKENS / GH_TOKEN or pass --github-tokens / --github-token."
        )

    gh = GitHubClient(pool=TokenPool(tokens))
    total = len(pending_indices)
    updated = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = {
            executor.submit(fetch_contributor_count, gh, str(df.at[index, "repo"])): index
            for index in pending_indices
        }
        for count, future in enumerate(as_completed(futures), start=1):
            index = futures[future]
            repo = str(df.at[index, "repo"])
            contributor_count, error = future.result()
            if contributor_count is None:
                errors += 1
                log.warning("Contributor fetch failed for %s: %s", repo, error)
            else:
                df.at[index, "contributors"] = contributor_count
                updated += 1

            if count % 100 == 0 or count == total:
                write_csv_atomically(df, out_csv)
                log.info("Contributor enrichment progress: %d/%d rows processed", count, total)

    log.info("Contributor enrichment complete: %d updated, %d failed", updated, errors)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
