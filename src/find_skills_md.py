#!/usr/bin/env python3
"""
find_skills_md.py

Scan GitHub repositories listed in a folder of SEART CSVs for a file named SKILL.md.
Writes a results CSV and (optionally) a shortlist CSV (found=true only).

Primary scan method:
- GitHub Contents API: GET /repos/{owner}/{repo}/contents/{path}?ref={default_branch}
  NOTE: This checks an exact path only (e.g. /SKILL.md checks the repo root).
  Use --enable-code-search to find SKILL.md in any subdirectory.

Optional fallback:
- GitHub Search Code API: GET /search/code?q=repo:owner/repo+filename:SKILL.md

Notes:
- Read-only.
- Supports resume by skipping repos already present in the output results CSV.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import json
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

log = logging.getLogger(__name__)


REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


# ----------------------------
# Data structures
# ----------------------------

@dataclasses.dataclass(frozen=True)
class RepoSource:
    repo: str               # owner/repo
    source_csv: str         # filename that contributed this repo (or MULTIPLE)


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


# ----------------------------
# GitHub client with backoff
# ----------------------------

class GitHubClient:
    def __init__(self, token: Optional[str], base_url: str = "https://api.github.com") -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            # Pinning to a stable API version header is recommended by GitHub docs.
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "skills-md-miner/1.0",
        })
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def _sleep_for_rate_limit(self, resp: requests.Response) -> None:
        # Primary rate limit exhausted
        remaining = resp.headers.get("X-RateLimit-Remaining")
        reset = resp.headers.get("X-RateLimit-Reset")  # epoch seconds
        if remaining == "0" and reset:
            try:
                reset_epoch = int(reset)
                now = int(time.time())
                wait_s = max(0, reset_epoch - now) + 2
                time.sleep(wait_s)
                return
            except Exception:
                pass

        # Secondary rate limits or abuse detection may provide Retry-After
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                time.sleep(int(retry_after))
                return
            except Exception:
                pass

        # Generic fallback
        time.sleep(60)

    def request_json(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        max_retries: int = 5,
        timeout_s: int = 30,
    ) -> Tuple[int, dict, str]:
        """
        Returns (status_code, json_dict_or_empty, error_message).
        Retries on 403/429 rate limiting and transient 5xx.
        """
        url = f"{self.base_url}{path}"
        backoff = 2.0

        for attempt in range(max_retries + 1):
            try:
                resp = self.session.request(method, url, params=params, timeout=timeout_s)
            except requests.RequestException as e:
                if attempt >= max_retries:
                    return (0, {}, f"network_error: {e}")
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue

            status = resp.status_code

            # Success
            if 200 <= status < 300:
                if resp.content:
                    try:
                        return (status, resp.json(), "")
                    except Exception:
                        return (status, {}, "json_parse_error")
                return (status, {}, "")

            # Not found or unauthorized: do not retry
            if status in (401, 404):
                msg = self._safe_error_message(resp)
                return (status, {}, msg)

            # Rate limiting or abuse throttling: retry with wait
            if status in (403, 429):
                msg = self._safe_error_message(resp)
                if attempt >= max_retries:
                    return (status, {}, msg)
                self._sleep_for_rate_limit(resp)
                continue

            # Transient server errors
            if 500 <= status <= 599:
                msg = self._safe_error_message(resp)
                if attempt >= max_retries:
                    return (status, {}, msg)
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue

            # Other errors: do not retry
            msg = self._safe_error_message(resp)
            return (status, {}, msg)

        return (0, {}, "unknown_error")

    @staticmethod
    def _safe_error_message(resp: requests.Response) -> str:
        try:
            data = resp.json()
            if isinstance(data, dict) and "message" in data:
                return str(data["message"])[:400]
        except Exception:
            pass
        return (resp.text or "").strip()[:400]


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

                if not extracted_any:
                    errors.append(f"{fname}: no repos extracted (unsupported schema or empty rows)")
        except Exception as e:
            errors.append(f"{fname}: failed to read CSV ({e})")

    repos: List[RepoSource] = []
    for repo, sources in sorted(repo_to_sources.items()):
        src = "MULTIPLE" if len(sources) > 1 else next(iter(sources))
        repos.append(RepoSource(repo=repo, source_csv=src))

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


def get_repo_metadata(gh: GitHubClient, repo: str) -> Tuple[Optional[dict], int, str]:
    owner, name = repo.split("/", 1)
    status, data, err = gh.request_json("GET", f"/repos/{owner}/{name}")
    if status == 200 and isinstance(data, dict):
        return (data, status, "")
    return (None, status, err)


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
    # Search API: q=repo:owner/repo filename:SKILLS.md
    q = f"repo:{repo} filename:{filename}"
    status, data, err = gh.request_json("GET", "/search/code", params={"q": q, "per_page": 10})
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
    search_paths: List[str],
    enable_code_search: bool,
    min_stars: int,
    allow_forks: bool,
    allow_archived: bool,
) -> ScanResult:
    scanned_at = utc_now_iso()

    # Defaults for output columns
    res = ScanResult(
        repo=repo_src.repo,
        source_csv=repo_src.source_csv,
        found=False,
        match_name=match_name,
        match_path="",
        default_branch="",
        ref_scanned="",
        match_url="",
        match_sha="",
        match_size_bytes="",
        scan_method="",
        http_status="",
        error_type="none",
        error_message="",
        scanned_at_utc=scanned_at,
        stars="",
        fork="",
        archived="",
    )

    meta, status, err = get_repo_metadata(gh, repo_src.repo)
    res.http_status = str(status) if status else "0"

    if not meta:
        res.error_type = classify_error(status, err)
        res.error_message = err
        return res

    default_branch = meta.get("default_branch") or ""
    stars = meta.get("stargazers_count")
    is_fork = meta.get("fork")
    is_archived = meta.get("archived")

    res.default_branch = str(default_branch)
    res.ref_scanned = str(default_branch)
    res.stars = "" if stars is None else str(stars)
    res.fork = "" if is_fork is None else str(bool(is_fork)).lower()
    res.archived = "" if is_archived is None else str(bool(is_archived)).lower()
    res.scan_method = "contents_api"

    # Apply filters
    try:
        if stars is not None and int(stars) < int(min_stars):
            res.error_type = "filtered"
            res.error_message = f"stars<{min_stars}"
            return res
    except Exception:
        pass

    if not allow_forks and bool(is_fork):
        res.error_type = "filtered"
        res.error_message = "fork"
        return res

    if not allow_archived and bool(is_archived):
        res.error_type = "filtered"
        res.error_message = "archived"
        return res

    # Tier A: Contents API checks for explicit paths
    for p in search_paths:
        ok, data, st, e = try_contents_path(gh, repo_src.repo, p, default_branch)
        res.http_status = str(st) if st else res.http_status

        if ok:
            res.found = True
            res.match_path = "/" + (data.get("path") or p.lstrip("/"))
            res.match_sha = str(data.get("sha") or "")
            res.match_size_bytes = str(data.get("size") or "")
            res.match_url = str(data.get("html_url") or "")
            res.error_type = "none"
            res.error_message = ""
            res.scan_method = "contents_api"
            return res

        # If auth/rate limiting happens here, keep the error and stop early
        if st in (401, 403, 429):
            res.error_type = classify_error(st, e)
            res.error_message = e
            return res

    # Optional Tier B: Code search to find SKILL.md in subdirs
    if enable_code_search:
        found, item, st, e = try_code_search(gh, repo_src.repo, match_name)
        res.http_status = str(st) if st else res.http_status

        if found and item:
            res.found = True
            res.scan_method = "code_search"

            # Search item fields
            path = item.get("path") or ""
            html_url = item.get("html_url") or ""
            sha = item.get("sha") or ""

            res.match_path = "/" + path.lstrip("/")
            res.match_url = str(html_url)
            res.match_sha = str(sha)
            res.error_type = "none"
            res.error_message = ""
            return res

        if st in (401, 403, 429):
            res.error_type = classify_error(st, e)
            res.error_message = e
            return res

    # Not found
    res.found = False
    res.error_type = "none"
    res.error_message = ""
    return res


# ----------------------------
# Resume, writing, shortlist
# ----------------------------

OUTPUT_COLUMNS = [
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
]


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
        writer.writerow(dataclasses.asdict(r))


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
    """Query /rate_limit, log status, and return the resources dict."""
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
    return resources


# ----------------------------
# CLI
# ----------------------------

def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Scan repos from SEART CSVs for SKILL.md. "
            "The default --search-path (/SKILL.md) checks the repo root only. "
            "Use --enable-code-search to find SKILL.md in any subdirectory."
        )
    )
    p.add_argument("--seart-dir", required=True, help="Directory containing SEART CSV exports")
    p.add_argument("--out-csv", required=True, help="Output results CSV path")
    p.add_argument("--shortlist-csv", default="", help="Optional shortlist CSV path (found=true only)")

    p.add_argument("--match-name", default="SKILL.md", help="Filename to search for")
    p.add_argument(
        "--search-path",
        action="append",
        default=[],
        help=(
            "Exact path to check with the Contents API; can be repeated. "
            "Example: /SKILL.md (root only). "
            "Use --enable-code-search to search all subdirectories instead."
        ),
    )
    p.add_argument("--enable-code-search", action="store_true", help="Use /search/code fallback")
    p.add_argument("--min-stars", type=int, default=0, help="Filter: require at least N stars")
    p.add_argument("--disallow-forks", action="store_true", help="Filter: skip forks")
    p.add_argument("--disallow-archived", action="store_true", help="Filter: skip archived repos")

    p.add_argument("--max-repos", type=int, default=0, help="Limit repos scanned (0 means no limit)")
    p.add_argument("--resume", action="store_true", help="Skip repos already in out-csv")
    p.add_argument("--include-negative-results", action="store_true", help="Write found=false rows too")
    p.add_argument("--concurrency", type=int, default=4, help="Worker threads. Lower if rate-limited.")
    p.add_argument("--github-token", default="", help="Overrides GH_TOKEN env var")
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

    token = args.github_token.strip() or os.getenv("GH_TOKEN", "").strip() or os.getenv("GITHUB_TOKEN", "").strip()
    if not token:
        log.warning(
            "No GitHub token detected. Unauthenticated limits: "
            "60 core requests/hour, 10 search requests/minute. "
            "Set GH_TOKEN or pass --github-token."
        )
    gh = GitHubClient(token=token)

    # Check and log current rate limit before starting.
    resources = check_rate_limit(gh)

    # Default search path if none provided.
    search_paths = args.search_path if args.search_path else ["/SKILL.md"]

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

    write_header_if_needed(args.out_csv)

    allow_forks = not args.disallow_forks
    allow_archived = not args.disallow_archived

    total = len(repos_to_scan)
    if total == 0:
        log.info("Nothing to scan (resume skipped everything).")
        if args.shortlist_csv:
            write_shortlist(args.out_csv, args.shortlist_csv)
        return 0

    # Warn if estimated request count exceeds remaining rate limit.
    reqs_needed = total * (1 + len(search_paths)) + (total if args.enable_code_search else 0)
    core_remaining = resources.get("core", {}).get("remaining", 0) if resources else 0
    if core_remaining and reqs_needed > core_remaining:
        log.warning(
            "Estimated API requests needed (%d) exceeds core rate limit remaining (%d). "
            "Consider --max-repos to scan in batches, or wait for rate limit reset.",
            reqs_needed, core_remaining,
        )

    log.info(
        "Scanning %d repositories | concurrency=%d | paths=%s | code_search=%s",
        total, args.concurrency, search_paths, args.enable_code_search,
    )

    found_count = 0
    error_counts: Dict[str, int] = {}
    scan_start = time.time()

    with ThreadPoolExecutor(max_workers=max(1, int(args.concurrency))) as ex:
        futures = {
            ex.submit(
                scan_one_repo,
                gh,
                repo_src,
                args.match_name,
                search_paths,
                bool(args.enable_code_search),
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
                        )

                    log.debug(
                        "%-50s found=%-5s error=%-14s method=%s",
                        r.repo, r.found, r.error_type, r.scan_method or "-",
                    )

                    if r.found:
                        found_count += 1
                    error_counts[r.error_type] = error_counts.get(r.error_type, 0) + 1

                    if r.found or args.include_negative_results:
                        append_result(args.out_csv, r)

                    pbar.update(1)
                    rl = error_counts.get("rate_limited", 0)
                    errs = sum(v for k, v in error_counts.items() if k not in ("none", "filtered", "rate_limited"))
                    pbar.set_postfix_str(
                        f"found={found_count} rl={rl} err={errs}",
                        refresh=False,
                    )

    elapsed = time.time() - scan_start

    if args.shortlist_csv:
        write_shortlist(args.out_csv, args.shortlist_csv)

    pct = 100.0 * found_count / total if total else 0.0
    log.info(
        "Done | elapsed=%.1fs | scanned=%d | found=%d (%.1f%%) | rate_limited=%d",
        elapsed, total, found_count, pct, error_counts.get("rate_limited", 0),
    )
    log.info("Error breakdown: %s", dict(sorted(error_counts.items())))
    log.info("Results CSV: %s", args.out_csv)
    if args.shortlist_csv:
        log.info("Shortlist CSV: %s", args.shortlist_csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
