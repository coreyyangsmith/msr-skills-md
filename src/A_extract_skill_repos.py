#!/usr/bin/env python3
"""
find_skills_md.py

Scan GitHub repositories listed in a folder of SEART CSVs for a file named SKILL.md
anywhere in the repository tree.

Scan strategy:
  One call per repo – GitHub Code Search API: full-repo filename search.
  ACF files (CLAUDE.md, AGENTS.md, copilot-instructions.md) are checked via the
  Contents API only for repositories where SKILL.md is confirmed found.
  Repo metadata (branch, stars, fork, archived) is read from SEART CSV data —
  no separate metadata API call is made.

Output: one comprehensive CSV (for resume) plus three category-split CSVs written
automatically next to it:
  *_found.csv      – repositories where SKILL.md was found
  *_not_found.csv  – repositories that were scanned cleanly with no match
  *_errors.csv     – repositories that hit any API error (rate-limit, network, auth, …)

Notes:
- Read-only.
- Supports resume by skipping repos already present in the output results CSV.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set, Tuple

from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from github_client import GitHubClient, TokenPool, load_tokens_from_env

log = logging.getLogger(__name__)


REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# All columns present in a SEART CSV export (order matches the export header).
SEART_COLUMNS: List[str] = [
    "id", "name", "isFork", "commits", "branches", "releases", "forks",
    "mainLanguage", "defaultBranch", "license", "homepage", "watchers",
    "stargazers", "contributors", "size", "createdAt", "pushedAt", "updatedAt",
    "totalIssues", "openIssues", "totalPullRequests", "openPullRequests",
    "blankLines", "codeLines", "commentLines", "metrics", "lastCommit",
    "lastCommitSHA", "hasWiki", "isArchived", "isDisabled", "isLocked",
    "languages", "labels", "topics",
]


# ----------------------------
# Data structures
# ----------------------------

@dataclasses.dataclass(frozen=True)
class RepoSource:
    repo: str               # owner/repo
    source_csv: str         # filename that contributed this repo (or MULTIPLE)
    seart_data: Dict[str, str] = dataclasses.field(
        default_factory=dict, hash=False, compare=False
    )


@dataclasses.dataclass
class ScanResult:
    repo: str
    source_csv: str
    found: bool
    match_name: str
    match_path: str
    default_branch: str
    ref_scanned: str
    match_url: str
    match_sha: str
    match_size_bytes: str
    scan_method: str
    http_status: str
    error_type: str
    error_message: str
    scanned_at_utc: str
    stars: str
    fork: str
    archived: str
    has_CLAUDE: str = "0"
    has_AGENTS: str = "0"
    has_COPILOT: str = "0"
    seart_data: Dict[str, str] = dataclasses.field(default_factory=dict)


# ----------------------------
# CSV ingest (SEART)
# ----------------------------

REPO_COLUMNS_PRIORITY = [
    "full_name",
    "repo",
    "repository",
    "name",       # SEART exports: name column contains owner/repo
]

URL_COLUMNS = ["html_url", "url"]

PAIR_COLUMN_SETS = [
    ("owner", "name"),
    ("org", "repo_name"),
    ("repo_owner", "repo_name"),
]


def list_csv_files(seart_dir: str) -> List[str]:
    paths: List[str] = []
    for root, _, files in os.walk(seart_dir):
        for f in files:
            if f.lower().endswith(".csv"):
                paths.append(os.path.join(root, f))
    paths.sort()
    return paths


def normalize_repo(value: str) -> Optional[str]:
    if not value:
        return None
    s = value.strip()

    # If URL-like, extract owner/repo
    if "github.com" in s:
        s = s.replace("http://", "").replace("https://", "")
        # github.com/owner/repo or github.com/owner/repo/...
        parts = s.split("/")
        try:
            idx = parts.index("github.com")
            if len(parts) > idx + 2:
                candidate = f"{parts[idx+1]}/{parts[idx+2]}"
                candidate = candidate.removesuffix(".git")
                candidate = candidate.strip()
                if REPO_RE.match(candidate):
                    return candidate
        except ValueError:
            # maybe starts directly with github.com
            if parts[0] == "github.com" and len(parts) >= 3:
                candidate = f"{parts[1]}/{parts[2]}".removesuffix(".git").strip()
                if REPO_RE.match(candidate):
                    return candidate

    s = s.removesuffix(".git")
    if REPO_RE.match(s):
        return s
    return None


def extract_repo_from_row(row: Dict[str, str]) -> Optional[str]:
    # Priority: direct repo columns
    for col in REPO_COLUMNS_PRIORITY:
        if col in row and row[col]:
            r = normalize_repo(row[col])
            if r:
                return r

    # Pair columns
    for a, b in PAIR_COLUMN_SETS:
        if a in row and b in row and row[a] and row[b]:
            candidate = f"{row[a].strip()}/{row[b].strip()}"
            r = normalize_repo(candidate)
            if r:
                return r

    # URL columns
    for col in URL_COLUMNS:
        if col in row and row[col]:
            r = normalize_repo(row[col])
            if r:
                return r

    return None


def ingest_seart_csvs(seart_dir: str) -> Tuple[List[RepoSource], List[str]]:
    csv_paths = list_csv_files(seart_dir)
    if not csv_paths:
        return ([], [f"No CSV files found under: {seart_dir}"])

    repo_to_sources: Dict[str, Set[str]] = {}
    # Store the first-seen SEART row for each repo so we can carry it through.
    repo_to_seart_data: Dict[str, Dict[str, str]] = {}
    errors: List[str] = []

    for path in csv_paths:
        fname = os.path.basename(path)
        try:
            with open(path, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    errors.append(f"{fname}: missing header row")
                    continue

                extracted_any = False
                for row in reader:
                    repo = extract_repo_from_row(row)
                    if not repo:
                        continue
                    extracted_any = True
                    repo_to_sources.setdefault(repo, set()).add(fname)
                    if repo not in repo_to_seart_data:
                        repo_to_seart_data[repo] = {
                            col: (row.get(col) or "") for col in SEART_COLUMNS
                        }

                if not extracted_any:
                    errors.append(f"{fname}: no repos extracted (unsupported schema or empty rows)")
        except Exception as e:
            errors.append(f"{fname}: failed to read CSV ({e})")

    repos: List[RepoSource] = []
    for repo, sources in sorted(repo_to_sources.items()):
        src = "MULTIPLE" if len(sources) > 1 else next(iter(sources))
        repos.append(RepoSource(
            repo=repo,
            source_csv=src,
            seart_data=repo_to_seart_data.get(repo, {}),
        ))

    return (repos, errors)


# ----------------------------
# Scanning logic
# ----------------------------

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def classify_error(status: int, message: str) -> str:
    msg = (message or "").lower()
    if status == 0:
        return "network"
    if status == 401:
        return "auth"
    if status == 404:
        return "invalid_repo" if "not found" in msg else "not_found"
    if status in (403, 429):
        return "rate_limited"
    return "other"


def _bool_seart(val: str) -> bool:
    """Interpret a SEART boolean string ('true'/'false'/'1'/'0') as a Python bool."""
    return str(val).strip().lower() in ("true", "1", "yes")


def try_contents_path(
    gh: GitHubClient,
    repo: str,
    path: str,
    ref: str,
) -> Tuple[bool, dict, int, str]:
    owner, name = repo.split("/", 1)
    # Contents API expects path without leading slash
    clean_path = path.lstrip("/")
    status, data, err = gh.request_json(
        "GET",
        f"/repos/{owner}/{name}/contents/{clean_path}",
        params={"ref": ref} if ref else None,
    )
    if status == 200 and isinstance(data, dict) and data.get("type") == "file":
        return (True, data, status, "")
    if status == 200 and isinstance(data, dict) and data.get("type") != "file":
        return (False, {}, status, "path_is_not_file")
    return (False, {}, status, err)


def try_code_search(
    gh: GitHubClient,
    repo: str,
    filename: str,
) -> Tuple[bool, Optional[dict], int, str]:
    # Search API: q=repo:owner/repo filename:SKILL.md
    q = f"repo:{repo} filename:{filename}"
    status, data, err = gh.request_json("GET", "/search/code", params={"q": q, "per_page": 10}, is_search=True)
    if status != 200 or not isinstance(data, dict):
        return (False, None, status, err)

    items = data.get("items") or []
    if not items:
        return (False, None, status, "")

    # Pick best candidate deterministically: shortest path, then lexicographic
    def key_fn(item: dict) -> Tuple[int, str]:
        p = item.get("path") or ""
        return (len(p), p)

    best = sorted(items, key=key_fn)[0]
    return (True, best, status, "")


def scan_one_repo(
    gh: GitHubClient,
    repo_src: RepoSource,
    match_name: str,
    min_stars: int,
    allow_forks: bool,
    allow_archived: bool,
) -> ScanResult:
    scanned_at = utc_now_iso()

    # Pull repo attributes from SEART data — no metadata API call needed.
    sd = repo_src.seart_data
    default_branch = sd.get("defaultBranch") or ""
    stars_raw = sd.get("stargazers") or ""
    fork_raw = sd.get("isFork") or ""
    archived_raw = sd.get("isArchived") or ""

    res = ScanResult(
        repo=repo_src.repo,
        source_csv=repo_src.source_csv,
        found=False,
        match_name=match_name,
        match_path="",
        default_branch=default_branch,
        ref_scanned=default_branch or "HEAD",
        match_url="",
        match_sha="",
        match_size_bytes="",
        scan_method="code_search",
        http_status="",
        error_type="none",
        error_message="",
        scanned_at_utc=scanned_at,
        stars=stars_raw,
        fork=fork_raw,
        archived=archived_raw,
        seart_data=dict(sd),
    )

    # Apply filters when SEART data is present.
    if stars_raw:
        try:
            if int(stars_raw) < min_stars:
                res.error_type = "filtered"
                res.error_message = f"stars<{min_stars}"
                return res
        except ValueError:
            pass

    if fork_raw and not allow_forks and _bool_seart(fork_raw):
        res.error_type = "filtered"
        res.error_message = "fork"
        return res

    if archived_raw and not allow_archived and _bool_seart(archived_raw):
        res.error_type = "filtered"
        res.error_message = "archived"
        return res

    # Single code-search call to detect SKILL.md anywhere in the repo tree.
    found, item, st, e = try_code_search(gh, repo_src.repo, match_name)
    res.http_status = str(st) if st else ""

    if st == 401:
        res.error_type = "auth"
        res.error_message = e
        return res

    if not (found and item):
        # Not found — done; ACF checks are skipped.
        res.found = False
        res.error_type = "none"
        res.error_message = ""
        return res

    # SKILL.md found — record match details.
    res.found = True
    res.match_path = "/" + (item.get("path") or "").lstrip("/")
    res.match_url = str(item.get("html_url") or "")
    res.match_sha = str(item.get("sha") or "")
    res.error_type = "none"
    res.error_message = ""

    # ACF checks — Contents API only, run only for repos that have SKILL.md.
    # Using the SEART-provided branch, or "HEAD" if not available.
    ref = default_branch or "HEAD"
    _acf_checks = [
        ("/CLAUDE.md",                       "has_CLAUDE"),
        ("/AGENTS.md",                       "has_AGENTS"),
        ("/.github/copilot-instructions.md", "has_COPILOT"),
    ]
    for _path, _attr in _acf_checks:
        _ok, _, _st, _e = try_contents_path(gh, repo_src.repo, _path, ref)
        if _st == 401:
            res.error_type = "auth"
            res.error_message = _e
            return res
        setattr(res, _attr, "1" if _ok else "0")

    return res


# ----------------------------
# Resume, writing, shortlist
# ----------------------------

_SCAN_COLUMNS = [
    "repo",
    "source_csv",
    "found",
    "match_name",
    "match_path",
    "default_branch",
    "ref_scanned",
    "match_url",
    "match_sha",
    "match_size_bytes",
    "scan_method",
    "http_status",
    "error_type",
    "error_message",
    "scanned_at_utc",
    "stars",
    "fork",
    "archived",
    "has_CLAUDE",
    "has_AGENTS",
    "has_COPILOT",
]

# Full output schema: scan columns first, then every original SEART column.
OUTPUT_COLUMNS = _SCAN_COLUMNS + SEART_COLUMNS


def load_already_scanned(out_csv: str) -> Set[str]:
    if not out_csv or not os.path.exists(out_csv):
        return set()
    scanned: Set[str] = set()
    try:
        with open(out_csv, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r = (row.get("repo") or "").strip()
                if r:
                    scanned.add(r)
    except Exception:
        return set()
    return scanned


def write_header_if_needed(out_csv: str) -> None:
    if os.path.exists(out_csv) and os.path.getsize(out_csv) > 0:
        return
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()


def append_result(out_csv: str, r: ScanResult) -> None:
    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        d = dataclasses.asdict(r)
        seart = d.pop("seart_data", {})
        d.update(seart)
        writer.writerow(d)


def write_shortlist(results_csv: str, shortlist_csv: str) -> None:
    os.makedirs(os.path.dirname(shortlist_csv) or ".", exist_ok=True)
    with open(results_csv, "r", newline="", encoding="utf-8") as fin, \
         open(shortlist_csv, "w", newline="", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in reader:
            if (row.get("found") or "").strip().lower() == "true":
                writer.writerow(row)


_ERROR_TYPES = frozenset({"rate_limited", "network", "auth", "invalid_repo", "not_found", "other"})


def result_category(r: ScanResult) -> str:
    """
    Classify a scan result into one of three output categories.

    Returns:
        "found"     – SKILL.md was located anywhere in the repository.
        "errors"    – Any API error occurred (rate_limited, network, auth, …).
        "not_found" – Repository was scanned cleanly; file was not present
                      (includes filtered-out repos).
    """
    if r.found:
        return "found"
    if r.error_type in _ERROR_TYPES:
        return "errors"
    return "not_found"


def split_csv_paths(out_csv: str) -> Tuple[str, str, str]:
    """
    Derive the three category CSV paths from the main output CSV path.

    Example: outputs/skill_md_scan_results.csv →
        outputs/skill_md_scan_results_found.csv
        outputs/skill_md_scan_results_not_found.csv
        outputs/skill_md_scan_results_errors.csv
    """
    base, ext = os.path.splitext(out_csv)
    return (
        f"{base}_found{ext}",
        f"{base}_not_found{ext}",
        f"{base}_errors{ext}",
    )


# ----------------------------
# Logging
# ----------------------------

def setup_logging(level: str = "INFO") -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=numeric,
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        stream=sys.stderr,
        force=True,
    )


def check_rate_limit(gh: GitHubClient) -> dict:
    """
    Query /rate_limit, log status, and return the resources dict.

    Also logs per-token pool stats when multiple tokens are configured.
    """
    status, data, err = gh.request_json("GET", "/rate_limit")
    if status != 200:
        log.warning("Could not check rate limit (HTTP %s): %s", status, err)
        return {}

    resources = data.get("resources", {})
    core = resources.get("core", {})
    search = resources.get("search", {})

    def fmt_reset(epoch: int) -> str:
        try:
            return dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc).strftime("%H:%MZ")
        except Exception:
            return "?"

    log.info(
        "Rate limits – core: %d/%d (resets %s) | search: %d/%d (resets %s)",
        core.get("remaining", 0), core.get("limit", 0), fmt_reset(core.get("reset", 0)),
        search.get("remaining", 0), search.get("limit", 0), fmt_reset(search.get("reset", 0)),
    )

    pool_stats = gh.pool.stats()
    if pool_stats["token_count"] > 1:
        log.info(
            "Token pool: %d token(s) | total_remaining=%d | total_requests=%d",
            pool_stats["token_count"],
            pool_stats["total_remaining"],
            pool_stats["total_requests"],
        )

    return resources


# ----------------------------
# CLI
# ----------------------------

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Scan repos from SEART CSVs for SKILL.md using the GitHub Code Search API. "
            "One search call is made per repo; ACF files are checked only for repos where "
            "SKILL.md is found. Repo metadata is read from SEART CSV data — no separate "
            "metadata API call is needed. "
            "Three category CSVs (_found, _not_found, _errors) are written automatically "
            "alongside --out-csv."
        )
    )
    p.add_argument("--seart-dir", required=True, help="Directory containing SEART CSV exports")
    p.add_argument("--out-csv", required=True, help="Output results CSV path (all rows, used for resume)")
    p.add_argument("--shortlist-csv", default="", help="Optional shortlist CSV path (found=true only; superseded by *_found.csv)")

    p.add_argument("--match-name", default="SKILL.md", help="Filename to search for (default: SKILL.md)")
    p.add_argument("--min-stars", type=int, default=0, help="Filter: require at least N stars (from SEART data)")
    p.add_argument("--disallow-forks", action="store_true", help="Filter: skip forks (from SEART data)")
    p.add_argument("--disallow-archived", action="store_true", help="Filter: skip archived repos (from SEART data)")

    p.add_argument("--max-repos", type=int, default=0, help="Limit repos scanned (0 means no limit)")
    p.add_argument("--resume", action="store_true", help="Skip repos already in out-csv")
    p.add_argument(
        "--include-negative-results",
        action="store_true",
        help="(No-op: every row is always written to out-csv for complete resume support.)",
    )
    p.add_argument("--concurrency", type=int, default=4, help="Worker threads. Lower if rate-limited.")
    p.add_argument("--github-token", default="", help="Single GitHub token (overrides env). Use --github-tokens for multiple.")
    p.add_argument(
        "--github-tokens",
        default="",
        help=(
            "Comma-separated GitHub tokens for parallel rate-limit pools. "
            "Example: --github-tokens ghp_token1,ghp_token2. "
            "Overrides GH_TOKENS env var."
        ),
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO). Use DEBUG for per-repo detail.",
    )

    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    setup_logging(args.log_level)

    # Resolve tokens: CLI flags take priority, then env vars.
    raw_tokens = args.github_tokens.strip() or args.github_token.strip()
    if raw_tokens:
        tokens = [t.strip() for t in raw_tokens.split(",") if t.strip()]
    else:
        tokens = load_tokens_from_env()

    if not tokens:
        log.warning(
            "No GitHub token detected. Unauthenticated limits: "
            "60 core requests/hour, 10 search requests/minute. "
            "Set GH_TOKENS / GH_TOKEN or pass --github-tokens / --github-token."
        )

    pool = TokenPool(tokens)
    gh = GitHubClient(pool=pool)

    # Check and log current rate limit before starting.
    resources = check_rate_limit(gh)

    log.info("Ingesting SEART CSVs from: %s", args.seart_dir)
    repos, ingest_errors = ingest_seart_csvs(args.seart_dir)
    for e in ingest_errors:
        log.warning("Ingest: %s", e)

    if not repos:
        log.error("No repositories extracted. Exiting.")
        return 2

    log.info("Extracted %d unique repositories.", len(repos))

    if args.max_repos and args.max_repos > 0:
        repos = repos[: args.max_repos]
        log.info("Capped to %d repositories (--max-repos).", args.max_repos)

    already = load_already_scanned(args.out_csv) if args.resume else set()
    if already:
        log.info("Resume: skipping %d already-scanned repositories.", len(already))
    repos_to_scan = [r for r in repos if r.repo not in already]

    # Prepare all output CSV paths: one comprehensive file + three category splits.
    found_csv, not_found_csv, errors_csv = split_csv_paths(args.out_csv)
    for path in (args.out_csv, found_csv, not_found_csv, errors_csv):
        write_header_if_needed(path)

    allow_forks = not args.disallow_forks
    allow_archived = not args.disallow_archived

    total = len(repos_to_scan)
    if total == 0:
        log.info("Nothing to scan (resume skipped everything).")
        if args.shortlist_csv:
            write_shortlist(args.out_csv, args.shortlist_csv)
        return 0

    # Estimate search API requests: 1 per repo (plus up to 3 ACF calls for found repos,
    # which use the core API and are negligible at ~2% hit rate).
    search_remaining = resources.get("search", {}).get("remaining", 0) if resources else 0
    if search_remaining and total > search_remaining:
        log.warning(
            "Estimated search requests needed (%d) exceeds search rate limit remaining (%d). "
            "The pool will sleep until quota resets and continue automatically.",
            total, search_remaining,
        )

    log.info(
        "Scanning %d repositories | concurrency=%d | method=code_search | match=%s",
        total, args.concurrency, args.match_name,
    )
    log.info(
        "Output CSVs: all=%s | found=%s | not_found=%s | errors=%s",
        args.out_csv, found_csv, not_found_csv, errors_csv,
    )

    # Per-category running counts for the tqdm postfix.
    found_count = 0
    not_found_count = 0
    rate_limited_count = 0
    error_count = 0          # non-rate-limit errors
    error_type_counts: Dict[str, int] = {}
    scan_start = time.time()

    with ThreadPoolExecutor(max_workers=max(1, int(args.concurrency))) as ex:
        futures = {
            ex.submit(
                scan_one_repo,
                gh,
                repo_src,
                args.match_name,
                int(args.min_stars),
                allow_forks,
                allow_archived,
            ): repo_src.repo
            for repo_src in repos_to_scan
        }

        with logging_redirect_tqdm():
            with tqdm(
                total=total,
                desc="Scanning",
                unit="repo",
                dynamic_ncols=True,
                file=sys.stderr,
            ) as pbar:
                for fut in as_completed(futures):
                    try:
                        r: ScanResult = fut.result()
                    except Exception as e:
                        repo = futures[fut]
                        log.exception("Unexpected error scanning %s", repo)
                        r = ScanResult(
                            repo=repo,
                            source_csv="",
                            found=False,
                            match_name=args.match_name,
                            match_path="",
                            default_branch="",
                            ref_scanned="",
                            match_url="",
                            match_sha="",
                            match_size_bytes="",
                            scan_method="",
                            http_status="0",
                            error_type="other",
                            error_message=f"exception: {e}",
                            scanned_at_utc=utc_now_iso(),
                            stars="",
                            fork="",
                            archived="",
                            seart_data={},
                        )

                    category = result_category(r)

                    log.debug(
                        "%-50s  found=%-5s  category=%-9s  error_type=%-14s  method=%-13s  path=%s",
                        r.repo, r.found, category, r.error_type,
                        r.scan_method or "-", r.match_path or "-",
                    )

                    # Update per-category counters.
                    if category == "found":
                        found_count += 1
                    elif category == "not_found":
                        not_found_count += 1
                    elif r.error_type == "rate_limited":
                        rate_limited_count += 1
                    else:
                        error_count += 1
                    error_type_counts[r.error_type] = error_type_counts.get(r.error_type, 0) + 1

                    # Always write every row to out_csv.
                    # This ensures a resume run (--resume) can skip everything
                    # already processed, regardless of outcome.
                    append_result(args.out_csv, r)

                    # Write to the appropriate category CSV (always, unconditionally).
                    if category == "found":
                        append_result(found_csv, r)
                    elif category == "not_found":
                        append_result(not_found_csv, r)
                    else:
                        append_result(errors_csv, r)

                    pbar.update(1)
                    pbar.set_postfix_str(
                        f"found={found_count}"
                        f"  not_found={not_found_count}"
                        f"  rate_limited={rate_limited_count}"
                        f"  errors={error_count}",
                        refresh=False,
                    )

    elapsed = time.time() - scan_start

    if args.shortlist_csv:
        write_shortlist(args.out_csv, args.shortlist_csv)

    scanned = found_count + not_found_count + rate_limited_count + error_count
    pct_found = 100.0 * found_count / scanned if scanned else 0.0
    pct_not_found = 100.0 * not_found_count / scanned if scanned else 0.0
    pct_errors = 100.0 * (rate_limited_count + error_count) / scanned if scanned else 0.0

    log.info(
        "Scan complete | elapsed=%.1fs | scanned=%d"
        " | found=%d (%.1f%%)"
        " | not_found=%d (%.1f%%)"
        " | rate_limited=%d"
        " | errors=%d"
        " | total_errors=%.1f%%",
        elapsed, scanned,
        found_count, pct_found,
        not_found_count, pct_not_found,
        rate_limited_count,
        error_count,
        pct_errors,
    )
    log.info("Error type breakdown: %s", dict(sorted(error_type_counts.items())))
    log.info("Output | all=%s", args.out_csv)
    log.info("Output | found=%s", found_csv)
    log.info("Output | not_found=%s", not_found_csv)
    log.info("Output | errors=%s", errors_csv)
    if args.shortlist_csv:
        log.info("Output | shortlist=%s", args.shortlist_csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
