#!/usr/bin/env python3
"""
Populate has_CURSORRULES_MD, has_INSTRUCTIONS_MD, and has_GEMINI using the GitHub
Contents API only (no code search), pinned to commit_sha/acf_ref from an
existing scan CSV.

Writes:
  - --out-skill-only: full scan-schema CSV (e.g. skill_md_scan_results_skill_only_new_acfs.csv)
  - --out-merged: main corpus CSV with three new columns inserted after has_COPILOT

Pass --dedupe-only to skip the GitHub API and just deduplicate an existing
--out-skill-only file in-place (one row per repo, keeping the latest scanned_at_utc).
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Tuple

from tqdm import tqdm

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from extract_skill_repos import OUTPUT_COLUMNS, try_contents_path
from github_client import GitHubClient, TokenPool, load_tokens_from_env

log = logging.getLogger(__name__)


def dedupe_csv(
    path: str,
    key: str = "repo",
    tiebreak: str = "scanned_at_utc",
) -> int:
    """Deduplicate a CSV in-place by `key`, keeping the row with the latest `tiebreak`.

    Returns the number of duplicate rows removed.
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    best: dict[str, dict] = {}
    for row in rows:
        k = (row.get(key) or "").strip()
        if not k:
            continue
        prev = best.get(k)
        if prev is None or (row.get(tiebreak, "") > prev.get(tiebreak, "")):
            best[k] = row

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(best.values())

    return len(rows) - len(best)

NEW_ACF_CHECKS: Tuple[Tuple[str, str], ...] = (
    ("/.cursorrules.md", "has_CURSORRULES_MD"),
    ("/.instructions.md", "has_INSTRUCTIONS_MD"),
    ("/GEMINI.md", "has_GEMINI"),
)


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def fetch_extended_acf(
    gh: GitHubClient,
    repo: str,
    ref: str,
) -> Tuple[Dict[str, str], str]:
    """Return flag dict for the three extended columns and optional error summary."""
    out: Dict[str, str] = {}
    errs: list[str] = []
    for path, attr in NEW_ACF_CHECKS:
        ok, _data, st, err = try_contents_path(gh, repo, path, ref)
        if st in (200, 404):
            out[attr] = "1" if ok else "0"
        else:
            out[attr] = ""
            errs.append(f"{path}:{st}:{err or ''}")
    return out, ";".join(errs)


def _worker(args: Tuple[GitHubClient, str, str, str]) -> Tuple[str, Dict[str, str], str]:
    gh, repo, ref, _ = args
    flags, err = fetch_extended_acf(gh, repo, ref)
    return repo, flags, err


def resolve_tokens(github_tokens: str, github_token: str) -> list[str]:
    raw = (github_tokens or "").strip() or (github_token or "").strip()
    if raw:
        return [t.strip() for t in raw.split(",") if t.strip()]
    return load_tokens_from_env()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Enrich scan CSV with extended ACF columns via Contents API.")
    p.add_argument(
        "--input-known",
        default="data/skill_only_scan/known_skill_repos.csv",
        help="Input CSV with found repos and commit_sha (skill-only corpus).",
    )
    p.add_argument(
        "--merge-into",
        default="outputs/skill_md_scan_results_with_contributors.csv",
        help="Full scan CSV to merge extended columns into.",
    )
    p.add_argument(
        "--out-skill-only",
        default="outputs/skill_md_scan_results_skill_only_new_acfs.csv",
        help="Output path for enriched skill-only scan rows (full OUTPUT_COLUMNS).",
    )
    p.add_argument(
        "--out-merged",
        default="outputs/skill_md_scan_results_with_contributors_extended.csv",
        help="Output path for merged full corpus with extended ACF columns.",
    )
    p.add_argument("--github-token", default="", help="Single token (optional; use --github-tokens for multiple).")
    p.add_argument("--github-tokens", default="", help="Comma-separated tokens (overrides GH_TOKENS when set).")
    p.add_argument("--concurrency", type=int, default=16, help="Parallel workers for Contents API.")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.add_argument(
        "--dedupe-only",
        action="store_true",
        help=(
            "Skip the GitHub API. Read --out-skill-only, deduplicate rows by repo "
            "(keeping the latest scanned_at_utc), and write the result back in-place."
        ),
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _configure_logging(args.log_level)

    if args.dedupe_only:
        target = args.out_skill_only
        if not Path(target).is_file():
            log.error("File not found: %s", target)
            return 2
        before = sum(1 for _ in open(target, encoding="utf-8")) - 1  # exclude header
        removed = dedupe_csv(target)
        after = before - removed
        log.info(
            "Deduped %s: %d rows -> %d rows (%d duplicates removed).",
            target, before, after, removed,
        )
        return 0

    tokens = resolve_tokens(args.github_tokens, args.github_token)
    if not tokens:
        raise SystemExit("No GitHub tokens found. Set GH_TOKENS or pass --github-tokens / --github-token.")
    pool = TokenPool(tokens)
    gh = GitHubClient(pool=pool)

    # Build work list: found repos with a ref for Contents API
    work: list[Tuple[str, str]] = []
    with open(args.input_known, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("found") or "").strip().lower() != "true":
                continue
            repo = (row.get("repo") or "").strip()
            if not repo:
                continue
            ref = (row.get("acf_ref") or row.get("commit_sha") or "").strip()
            if not ref:
                ref = (row.get("default_branch") or "HEAD").strip()
            work.append((repo, ref))

    log.info("Extended ACF checks for %d found repositories (3 Contents calls each).", len(work))

    acf_by_repo: Dict[str, Dict[str, str]] = {}
    errors_n = 0
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futures = {
            ex.submit(_worker, (gh, repo, ref, repo)): repo
            for repo, ref in work
        }
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Contents API ACF"):
            repo = futures[fut]
            try:
                rrepo, flags, err = fut.result()
                acf_by_repo[rrepo] = flags
                if err:
                    errors_n += 1
                    log.debug("%s: %s", rrepo, err)
            except Exception as e:
                log.warning("Failed %s: %s", repo, e)
                acf_by_repo[repo] = {
                    "has_CURSORRULES_MD": "",
                    "has_INSTRUCTIONS_MD": "",
                    "has_GEMINI": "",
                }

    if errors_n:
        log.warning("Non-404/200 responses on at least one path for %d repos (flags may be empty).", errors_n)

    # --- Write skill-only enriched CSV (full schema) ---
    Path(args.out_skill_only).resolve().parent.mkdir(parents=True, exist_ok=True)
    with open(args.input_known, newline="", encoding="utf-8") as fin, open(
        args.out_skill_only, "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in reader:
            repo = (row.get("repo") or "").strip()
            flags = acf_by_repo.get(repo)
            if flags:
                row.update(flags)
            else:
                row.setdefault("has_CURSORRULES_MD", "0")
                row.setdefault("has_INSTRUCTIONS_MD", "0")
                row.setdefault("has_GEMINI", "0")
            # Normalise keys for OUTPUT_COLUMNS
            out_row = {k: row.get(k, "") for k in OUTPUT_COLUMNS}
            writer.writerow(out_row)

    log.info("Wrote skill-only extended scan: %s", args.out_skill_only)

    removed = dedupe_csv(args.out_skill_only)
    if removed:
        log.info("Deduped skill-only CSV: removed %d duplicate rows.", removed)

    # --- Merge into full contributors CSV ---
    merge_path = Path(args.merge_into)
    if not merge_path.is_file():
        log.error("Merge input not found: %s", merge_path)
        return 2

    insert_after = "has_COPILOT"
    new_cols = ["has_CURSORRULES_MD", "has_INSTRUCTIONS_MD", "has_GEMINI"]

    with open(merge_path, newline="", encoding="utf-8", errors="replace") as fin:
        reader = csv.DictReader(fin)
        if not reader.fieldnames:
            log.error("Empty or unreadable merge CSV.")
            return 2
        fieldnames = list(reader.fieldnames)
        if insert_after not in fieldnames:
            log.error("Column %r not found in merge CSV.", insert_after)
            return 2
        # Avoid duplicating if re-run
        for c in new_cols:
            if c in fieldnames:
                fieldnames.remove(c)
        idx = fieldnames.index(insert_after) + 1
        for j, c in enumerate(new_cols):
            fieldnames.insert(idx + j, c)

        rows_out: list[dict[str, str]] = []
        for row in reader:
            repo = (row.get("repo") or "").strip()
            flags = acf_by_repo.get(repo)
            if flags:
                row.update(flags)
            else:
                for c in new_cols:
                    row[c] = "0"
            rows_out.append({k: row.get(k, "") for k in fieldnames})

    out_merged = Path(args.out_merged)
    out_merged.parent.mkdir(parents=True, exist_ok=True)
    with open(out_merged, "w", newline="", encoding="utf-8") as fout:
        w = csv.DictWriter(fout, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows_out)

    log.info("Wrote merged corpus with extended ACF columns: %s", out_merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
