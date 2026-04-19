#!/usr/bin/env python3
"""
extract_skill_repos.py

Scan GitHub repositories listed in a folder of SEART CSVs for a file named SKILL.md
anywhere in the repository tree.

Scan strategy:
  One call per repo – GitHub Community Profile API: maintainer-readiness metadata
  (README / CONTRIBUTING / SECURITY / CODE_OF_CONDUCT presence). This call is
  treated as optional enrichment; failure does not block the SKILL.md scan.
  One call per repo – GitHub Code Search API: full-repo filename search.
  ACF files (CLAUDE.md, AGENTS.md, copilot-instructions.md, .cursorrules.md,
  .instructions.md, GEMINI.md) are checked via the Contents API only for
  repositories where SKILL.md is confirmed found. ACF check failures are
  recorded separately and do not affect the primary found/not-found
  classification.
  Repo metadata (branch, stars, fork, archived) is read from SEART CSV data —
  no separate metadata API call is made.

No repo filtering is applied here — every repo in the SEART CSVs is scanned
(subject only to the optional blacklist). Filtering for downstream analysis is
handled in generate_dataset.py.

Output: one comprehensive CSV (for resume) plus four category-split CSVs written
automatically next to it:
  *_found.csv      – repositories where SKILL.md was found
  *_not_found.csv  – repositories that were scanned cleanly with no match
  *_errors.csv     – repositories that hit any API error (rate-limit, network, auth, …)
  *_filtered.csv   – repositories skipped by the optional blacklist

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
from urllib.parse import quote

from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from github_client import GitHubClient, TokenPool, load_tokens_from_env

log = logging.getLogger(__name__)


REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

COMMUNITY_PROFILE_FILE_FLAGS: Dict[str, str] = {
    "readme": "has_README",
    "contributing": "has_CONTRIBUTING",
    "security": "has_SECURITY",
    "code_of_conduct": "has_CODE_OF_CONDUCT",
}

ACF_CONTENTS_CHECKS: List[Tuple[str, str]] = [
    ("/CLAUDE.md", "has_CLAUDE"),
    ("/AGENTS.md", "has_AGENTS"),
    ("/.github/copilot-instructions.md", "has_COPILOT"),
    ("/.cursorrules.md", "has_CURSORRULES_MD"),
    ("/.instructions.md", "has_INSTRUCTIONS_MD"),
    ("/GEMINI.md", "has_GEMINI"),
]

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
    seart_default_branch: str   # branch hint from SEART CSV (not a precise searched ref)
    commit_sha: str             # pinned commit SHA at the scanned branch tip
    acf_ref: str                # actual ref used for ACF Contents API calls (SHA or branch)
    match_url: str
    match_sha: str
    match_size_bytes: str
    scan_method: str
    http_status: str
    error_type: str
    error_message: str
    acf_error_type: str         # error from ACF checks (separate from primary scan error)
    acf_error_message: str
    scanned_at_utc: str
    stars: str
    fork: str
    archived: str
    has_README: str = "0"
    has_CONTRIBUTING: str = "0"
    has_SECURITY: str = "0"
    has_CODE_OF_CONDUCT: str = "0"
    has_CLAUDE: str = "0"
    has_AGENTS: str = "0"
    has_COPILOT: str = "0"
    has_CURSORRULES_MD: str = "0"
    has_INSTRUCTIONS_MD: str = "0"
    has_GEMINI: str = "0"
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


def resolve_commit_sha(
    gh: GitHubClient,
    repo: str,
    ref: str,
) -> str:
    """
    Resolve a branch name or ref to a full commit SHA.

    Uses GET /repos/{owner}/{repo}/commits/{ref}. Returns the 40-char SHA on
    success, or "" on failure so the caller can fall back to branch-based tree
    fetches for legacy rows.
    """
    if not ref:
        return ""
    owner, name = repo.split("/", 1)
    ref_quoted = quote(ref, safe="")
    status, data, err = gh.request_json(
        "GET",
        f"/repos/{owner}/{name}/commits/{ref_quoted}",
    )
    if status == 200 and isinstance(data, str) and len(data) >= 40:
        return data[:40]
    # Fall back: standard JSON response also has .sha at the top level
    if status == 200 and isinstance(data, dict):
        sha = data.get("sha") or ""
        if sha:
            return sha
    log.debug("resolve_commit_sha: %s ref=%s status=%s err=%s", repo, ref, status, err)
    return ""


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


def try_community_profile(
    gh: GitHubClient,
    repo: str,
) -> Tuple[Dict[str, str], int, str]:
    owner, name = repo.split("/", 1)
    status, data, err = gh.request_json(
        "GET",
        f"/repos/{owner}/{name}/community/profile",
    )
    if status != 200 or not isinstance(data, dict):
        return ({}, status, err)

    files = data.get("files") or {}
    flags = {
        attr: "1" if files.get(api_name) else "0"
        for api_name, attr in COMMUNITY_PROFILE_FILE_FLAGS.items()
    }
    return (flags, status, "")


def try_code_search(
    gh: GitHubClient,
    repo: str,
    filename: str,
) -> Tuple[bool, Optional[dict], int, str]:
    # Search API: q=repo:owner/repo filename:SKILL.md
    q = f"repo:{repo} filename:{filename}"
    status, data, err = gh.request_json("GET", "/search/code", params={"q": q, "per_page": 100}, is_search=True)
    if status != 200 or not isinstance(data, dict):
        return (False, None, status, err)

    items = data.get("items") or []
    if not items:
        return (False, None, status, "")

    # GitHub Code Search is case-insensitive, so filter to exact-case basename matches.
    items = [item for item in items if os.path.basename(item.get("path") or "") == filename]
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
        seart_default_branch=default_branch or "HEAD",
        commit_sha="",
        acf_ref="",
        match_url="",
        match_sha="",
        match_size_bytes="",
        scan_method="code_search",
        http_status="",
        error_type="none",
        error_message="",
        acf_error_type="",
        acf_error_message="",
        scanned_at_utc=scanned_at,
        stars=stars_raw,
        fork=fork_raw,
        archived=archived_raw,
        seart_data=dict(sd),
    )

    # Community profile is optional enrichment — failure does not block the scan.
    community_flags, community_status, community_err = try_community_profile(gh, repo_src.repo)
    if community_status == 200:
        for attr, value in community_flags.items():
            setattr(res, attr, value)
    else:
        log.debug(
            "Community profile unavailable for %s (HTTP %s), continuing with code search: %s",
            repo_src.repo, community_status, community_err,
        )

    # Single code-search call to detect SKILL.md anywhere in the repo tree.
    found, item, st, e = try_code_search(gh, repo_src.repo, match_name)
    res.http_status = str(st) if st else ""

    if st != 200:
        res.error_type = classify_error(st, e)
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

    # Resolve the exact commit SHA at the scanned branch tip so later stages can
    # query the same tree instead of a potentially-moved branch head.
    ref = default_branch or "HEAD"
    res.commit_sha = resolve_commit_sha(gh, repo_src.repo, ref)

    # Use the pinned SHA for all Contents API calls when available; fall back to
    # the branch name so results are consistent with the code-search snapshot.
    acf_ref = res.commit_sha or ref
    res.acf_ref = acf_ref

    # Fetch the SKILL.md file via Contents API to record its size in bytes.
    _size_ok, _size_data, _size_st, _size_e = try_contents_path(
        gh, repo_src.repo, res.match_path, acf_ref
    )
    if _size_ok and _size_data:
        res.match_size_bytes = str(_size_data.get("size", ""))

    # ACF checks — Contents API only, run only for repos that have SKILL.md.
    # Failures are recorded in acf_error_type/acf_error_message and do not
    # affect the primary found/not-found classification.
    for _path, _attr in ACF_CONTENTS_CHECKS:
        _ok, _, _st, _e = try_contents_path(gh, repo_src.repo, _path, acf_ref)
        if _st not in (200, 404):
            res.acf_error_type = classify_error(_st, _e)
            res.acf_error_message = _e
            log.debug(
                "ACF check failed for %s path=%s status=%s: %s",
                repo_src.repo, _path, _st, _e,
            )
            setattr(res, _attr, "")  # unknown — not "0" (confirmed absent)
        else:
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
    "seart_default_branch",
    "commit_sha",
    "acf_ref",
    "match_url",
    "match_sha",
    "match_size_bytes",
    "scan_method",
    "http_status",
    "error_type",
    "error_message",
    "acf_error_type",
    "acf_error_message",
    "scanned_at_utc",
    "stars",
    "fork",
    "archived",
    "has_README",
    "has_CONTRIBUTING",
    "has_SECURITY",
    "has_CODE_OF_CONDUCT",
    "has_CLAUDE",
    "has_AGENTS",
    "has_COPILOT",
    "has_CURSORRULES_MD",
    "has_INSTRUCTIONS_MD",
    "has_GEMINI",
]

# Full output schema: scan columns first, then every original SEART column.
OUTPUT_COLUMNS = _SCAN_COLUMNS + SEART_COLUMNS


def load_blacklist(path: str) -> Set[str]:
    """Load a blacklist file and return a set of 'owner/repo' strings to skip."""
    if not path or not os.path.exists(path):
        return set()
    blacklisted: Set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            entry = line.strip()
            if entry and not entry.startswith("#"):
                blacklisted.add(entry)
    if blacklisted:
        log.info("Blacklist loaded: %d entries from %s", len(blacklisted), path)
    return blacklisted


def validate_existing_output_header(out_csv: str) -> None:
    if not out_csv or not os.path.exists(out_csv) or os.path.getsize(out_csv) == 0:
        return
    with open(out_csv, "r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, [])
    if header != OUTPUT_COLUMNS:
        raise ValueError(
            f"Resume schema mismatch for {out_csv}. "
            "The existing output CSV header does not match the current schema; "
            "start with a fresh output file."
        )


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
    Classify a scan result into one of four output categories.

    Returns:
        "found"    – SKILL.md was located anywhere in the repository.
        "errors"   – Any primary API error occurred (rate_limited, network, auth, …).
                     Note: ACF-only errors do not affect this classification; a repo
                     with found=True and acf_error_type set still returns "found".
        "filtered" – Repository was skipped by policy (stars, fork, archived filters).
        "not_found"– Repository was scanned cleanly; file was not present.
    """
    if r.error_type in _ERROR_TYPES:
        return "errors"
    if r.found:
        return "found"
    if r.error_type == "filtered":
        return "filtered"
    return "not_found"


def split_csv_paths(out_csv: str) -> Tuple[str, str, str, str]:
    """
    Derive the four category CSV paths from the main output CSV path.

    Example: outputs/skill_md_scan_results.csv →
        outputs/skill_md_scan_results_found.csv
        outputs/skill_md_scan_results_not_found.csv
        outputs/skill_md_scan_results_errors.csv
        outputs/skill_md_scan_results_filtered.csv
    """
    base, ext = os.path.splitext(out_csv)
    return (
        f"{base}_found{ext}",
        f"{base}_not_found{ext}",
        f"{base}_errors{ext}",
        f"{base}_filtered{ext}",
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
            "Scan all repos from SEART CSVs for SKILL.md using the GitHub Community Profile and "
            "Code Search APIs. No repo filtering is applied; every repo is scanned to get a total "
            "population count. Filtering for downstream analysis is handled in generate_dataset.py. "
            "The community-profile call is optional enrichment; failure does not block the SKILL.md "
            "scan. One code-search call is made per repo; ACF files are checked only for repos where "
            "SKILL.md is found (ACF failures are recorded separately and do not affect the "
            "found/not-found classification). "
            "Repo metadata is read from SEART CSV data — no separate metadata API call is needed. "
            "Four category CSVs (_found, _not_found, _errors, _filtered) are written automatically "
            "alongside --out-csv."
        )
    )
    p.add_argument("--seart-dir", required=True, help="Directory containing SEART CSV exports")
    p.add_argument("--out-csv", required=True, help="Output results CSV path (all rows, used for resume)")
    p.add_argument("--shortlist-csv", default="", help="Optional shortlist CSV path (found=true only; superseded by *_found.csv)")

    p.add_argument("--match-name", default="SKILL.md", help="Filename to search for (default: SKILL.md)")

    p.add_argument("--max-repos", type=int, default=0, help="Limit repos scanned (0 means no limit)")
    p.add_argument("--blacklist", default="blacklist.txt", help="Path to blacklist file (owner/repo per line). Default: blacklist.txt")
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

    if args.resume:
        try:
            validate_existing_output_header(args.out_csv)
        except ValueError as exc:
            log.error(str(exc))
            return 2
    already = load_already_scanned(args.out_csv) if args.resume else set()
    if already:
        log.info("Resume: skipping %d already-scanned repositories.", len(already))

    blacklist = load_blacklist(args.blacklist)

    repos_to_scan = []
    skipped_blacklist = 0
    for r in repos:
        if r.repo in already:
            continue
        if r.repo in blacklist:
            skipped_blacklist += 1
            continue
        repos_to_scan.append(r)

    if blacklist:
        log.info("Blacklist: skipping %d blacklisted repositories.", skipped_blacklist)

    # Prepare all output CSV paths: one comprehensive file + four category splits.
    found_csv, not_found_csv, errors_csv, filtered_csv = split_csv_paths(args.out_csv)
    for path in (args.out_csv, found_csv, not_found_csv, errors_csv, filtered_csv):
        write_header_if_needed(path)

    total = len(repos_to_scan)
    if total == 0:
        log.info("Nothing to scan (resume skipped everything).")
        if args.shortlist_csv:
            write_shortlist(args.out_csv, args.shortlist_csv)
        return 0

    # Estimate search API requests: 1 per repo (plus up to len(ACF_CONTENTS_CHECKS)
    # core-API ACF calls for found repos, which are negligible at current hit rates).
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
        "Output CSVs: all=%s | found=%s | not_found=%s | errors=%s | filtered=%s",
        args.out_csv, found_csv, not_found_csv, errors_csv, filtered_csv,
    )

    # Per-category running counts for the tqdm postfix.
    found_count = 0
    not_found_count = 0
    filtered_count = 0
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
                            seart_default_branch="",
                            commit_sha="",
                            acf_ref="",
                            match_url="",
                            match_sha="",
                            match_size_bytes="",
                            scan_method="",
                            http_status="0",
                            error_type="other",
                            error_message=f"exception: {e}",
                            acf_error_type="",
                            acf_error_message="",
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
                    elif category == "filtered":
                        filtered_count += 1
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
                    elif category == "filtered":
                        append_result(filtered_csv, r)
                    else:
                        append_result(errors_csv, r)

                    pbar.update(1)
                    pbar.set_postfix_str(
                        f"found={found_count}"
                        f"  not_found={not_found_count}"
                        f"  filtered={filtered_count}"
                        f"  rate_limited={rate_limited_count}"
                        f"  errors={error_count}",
                        refresh=False,
                    )

    elapsed = time.time() - scan_start

    if args.shortlist_csv:
        write_shortlist(args.out_csv, args.shortlist_csv)

    scanned = found_count + not_found_count + filtered_count + rate_limited_count + error_count
    pct_found = 100.0 * found_count / scanned if scanned else 0.0
    pct_not_found = 100.0 * not_found_count / scanned if scanned else 0.0
    pct_filtered = 100.0 * filtered_count / scanned if scanned else 0.0
    pct_errors = 100.0 * (rate_limited_count + error_count) / scanned if scanned else 0.0

    log.info(
        "Scan complete | elapsed=%.1fs | scanned=%d"
        " | found=%d (%.1f%%)"
        " | not_found=%d (%.1f%%)"
        " | filtered=%d (%.1f%%)"
        " | rate_limited=%d"
        " | errors=%d"
        " | total_errors=%.1f%%",
        elapsed, scanned,
        found_count, pct_found,
        not_found_count, pct_not_found,
        filtered_count, pct_filtered,
        rate_limited_count,
        error_count,
        pct_errors,
    )
    log.info("Error type breakdown: %s", dict(sorted(error_type_counts.items())))
    log.info("Output | all=%s", args.out_csv)
    log.info("Output | found=%s", found_csv)
    log.info("Output | not_found=%s", not_found_csv)
    log.info("Output | errors=%s", errors_csv)
    log.info("Output | filtered=%s", filtered_csv)
    if args.shortlist_csv:
        log.info("Output | shortlist=%s", args.shortlist_csv)

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
