#!/usr/bin/env python3
"""
search_github_repos.py

Alternative to SEART CSV ingestion: scrape GitHub repositories directly using
the GitHub REST API (GET /search/repositories) and emit a SEART-compatible CSV
that feeds into the existing pipeline (extract_skill_repos.py + generate_dataset.py).

Criteria applied by default:
  - 10 or more stars
  - MIT, Apache 2.0, BSD-3-Clause, or BSD-2-Clause license
  - TypeScript, Python, C#, Go, C++, JavaScript, Java, C, or PHP
  - Pushed since 2025-10-16

API behaviour:
  - GET /search/repositories returns at most 1,000 results per query.
  - Rate limit: 30 requests/minute per authenticated token for /search/repositories.
  - Queries are split by (language, license) pair — 36 combinations by default.
  - When a combination still yields >= 1,000 results, the star range is
    recursively bisected until each sub-range returns < 1,000 results.
    This continues down to single-star-count ranges; if a single value still
    has >= 1,000 repos, the 1,000-result cap is accepted with a warning (this
    is extremely unlikely in practice).

Output CSV schema matches SEART exports so that extract_skill_repos.py and
generate_dataset.py can consume it unchanged.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import os
import re
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterator, List, Optional, Set, Tuple

from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from github_client import GitHubClient, SearchThrottle, TokenPool, load_tokens_from_env

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_LANGUAGES = [
    "TypeScript", "Python", "C#", "Go", "C++",
    "JavaScript", "Java", "C", "PHP", "Rust",
]

DEFAULT_LICENSES = [
    "mit",
    "apache-2.0",
    "bsd-3-clause",
    "bsd-2-clause",
]

DEFAULT_MIN_STARS = 10
DEFAULT_PUSHED_SINCE = "2025-10-16"

# Static star brackets.  The last bracket uses a sentinel high value so
# _build_query emits "stars:>=5000" rather than "stars:5000..10000000".
_STAR_HIGH_SENTINEL = 10_000_000

STAR_BRACKETS: List[Tuple[int, int]] = [
    (10,   14),
    (15,   19),
    (20,   29),
    (30,   49),
    (50,   74),
    (75,   99),
    (100, 149),
    (150, 199),
    (200, 299),
    (300, 499),
    (500, 749),
    (750, 999),
    (1000, 1999),
    (2000, 4999),
    (5000, 9999),
    (10000, _STAR_HIGH_SENTINEL),
]

# ---------------------------------------------------------------------------
# SEART CSV columns (mirrors extract_skill_repos.py)
# ---------------------------------------------------------------------------

SEART_COLUMNS: List[str] = [
    "id", "name", "isFork", "commits", "branches", "releases", "forks",
    "mainLanguage", "defaultBranch", "license", "homepage", "watchers",
    "stargazers", "contributors", "size", "createdAt", "pushedAt", "updatedAt",
    "totalIssues", "openIssues", "totalPullRequests", "openPullRequests",
    "blankLines", "codeLines", "commentLines", "metrics", "lastCommit",
    "lastCommitSHA", "hasWiki", "isArchived", "isDisabled", "isLocked",
    "languages", "labels", "topics",
]

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _repo_search_throttle() -> SearchThrottle:
    """Return a SearchThrottle tuned for /search/repositories (30 req/min)."""
    return SearchThrottle(max_per_minute=30, window_s=60.0)


def _build_query(
    language: str,
    license_key: str,
    pushed_start: str,
    star_low: int,
    star_high: int,
    pushed_end: str = "",
) -> str:
    """
    Build a GitHub repository search query string.

    - When star_high >= _STAR_HIGH_SENTINEL the upper bound is omitted,
      producing "stars:>=star_low" instead of "stars:star_low..star_high".
    - When pushed_end is provided the date qualifier becomes
      "pushed:pushed_start..pushed_end" (windowed mode), otherwise
      "pushed:>=pushed_start" (open-ended mode).
    """
    stars_q = (
        f"stars:>={star_low}"
        if star_high >= _STAR_HIGH_SENTINEL
        else f"stars:{star_low}..{star_high}"
    )
    date_q = (
        f"pushed:{pushed_start}..{pushed_end}"
        if pushed_end
        else f"pushed:>={pushed_start}"
    )
    return f'{stars_q} language:"{language}" license:{license_key} {date_q}'


_REPO_SEARCH_THROTTLE_KEY = "repo_search"


def _fetch_page(
    gh: GitHubClient,
    throttle: SearchThrottle,
    query: str,
    page: int,
    per_page: int = 100,
) -> Tuple[int, List[dict], int, bool]:
    """
    Fetch one page of repository search results.

    Returns (total_count, items, http_status, incomplete_results).
    """
    # Proactively throttle before the request using a fixed per-process key.
    # /search/repositories allows 30 req/min per token; using a single global
    # window is conservative (correct for 1 token, safe for multiple).
    throttle.wait_if_needed(_REPO_SEARCH_THROTTLE_KEY)

    status, data, err = gh.request_json(
        "GET",
        "/search/repositories",
        params={"q": query, "per_page": per_page, "page": page},
        is_search=False,  # use core rate-limit headers, not code-search headers
    )

    if status != 200 or not isinstance(data, dict):
        log.warning("Search HTTP %d for query=%r page=%d: %s", status, query, page, err)
        return 0, [], status, False

    total = int(data.get("total_count", 0))
    items = data.get("items") or []
    incomplete = bool(data.get("incomplete_results", False))
    return total, items, status, incomplete


def _repo_to_seart_row(repo: dict) -> Dict[str, str]:
    """Map a GitHub repository search-result object to a SEART-column dict."""
    license_obj = repo.get("license") or {}
    license_str = license_obj.get("spdx_id") or license_obj.get("name") or ""

    topics = repo.get("topics") or []
    topics_str = ";".join(topics)

    # SEART stores topics as a semicolon-joined string; labels are not available
    # from the search API so we leave them empty.
    return {
        "id":                str(repo.get("id", "")),
        "name":              repo.get("full_name", ""),
        "isFork":            str(repo.get("fork", False)).lower(),
        "commits":           "",
        "branches":          "",
        "releases":          "",
        "forks":             str(repo.get("forks_count", "")),
        "mainLanguage":      repo.get("language") or "",
        "defaultBranch":     repo.get("default_branch") or "",
        "license":           license_str,
        "homepage":          repo.get("homepage") or "",
        "watchers":          str(repo.get("watchers_count", "")),
        "stargazers":        str(repo.get("stargazers_count", "")),
        "contributors":      "",
        "size":              str(repo.get("size", "")),
        "createdAt":         repo.get("created_at") or "",
        "pushedAt":          repo.get("pushed_at") or "",
        "updatedAt":         repo.get("updated_at") or "",
        # open_issues_count from the search API counts open issues AND open PRs
        # combined, so it cannot serve as totalIssues.  Leave totalIssues empty
        # to be filled by the enrichment phase; openIssues is a best-effort
        # approximation from the search result.
        "totalIssues":       "",
        "openIssues":        str(repo.get("open_issues_count", "")),
        "totalPullRequests": "",
        "openPullRequests":  "",
        "blankLines":        "",
        "codeLines":         "",
        "commentLines":      "",
        "metrics":           "",
        "lastCommit":        repo.get("pushed_at") or "",
        "lastCommitSHA":     "",
        "hasWiki":           str(repo.get("has_wiki", False)).lower(),
        "isArchived":        str(repo.get("archived", False)).lower(),
        "isDisabled":        str(repo.get("disabled", False)).lower(),
        "isLocked":          "",
        "languages":         "",
        "labels":            "",
        "topics":            topics_str,
    }


# ---------------------------------------------------------------------------
# Core fetch logic — star brackets + biweekly subdivision
# ---------------------------------------------------------------------------

def _biweekly_windows(pushed_since: str, end_date: dt.date | None = None) -> List[Tuple[str, str]]:
    """
    Generate (start, end) ISO date string pairs from pushed_since to end_date
    in 7-day (1-week) windows.

    The first window starts on pushed_since; each subsequent window starts
    the day after the previous one ends.  The last window is clamped to
    end_date (defaults to today when not provided).
    """
    start = dt.date.fromisoformat(pushed_since)
    ceiling = end_date if end_date is not None else dt.date.today()
    windows: List[Tuple[str, str]] = []
    cur = start
    while cur <= ceiling:
        end = min(cur + dt.timedelta(days=6), ceiling)
        windows.append((cur.isoformat(), end.isoformat()))
        if end >= ceiling:
            break
        cur = end + dt.timedelta(days=1)
    return windows


def _paginate_query(
    gh: GitHubClient,
    throttle: SearchThrottle,
    query: str,
    already_seen: Set[str],
    first_page_items: List[dict],
    label: str,
) -> Iterator[dict]:
    """
    Yield repos from the already-fetched page 1, then continue paginating.

    Deduplicates against already_seen (updated in place).
    """
    per_page = 100

    def _emit(items: List[dict]) -> Iterator[dict]:
        for repo in items:
            full_name = repo.get("full_name", "")
            if full_name and full_name not in already_seen:
                already_seen.add(full_name)
                yield repo

    yield from _emit(first_page_items)

    if len(first_page_items) < per_page:
        return  # only one page

    for page in range(2, 11):  # pages 2–10 (hard cap: 100 × 10 = 1,000)
        _, items, status, incomplete = _fetch_page(gh, throttle, query, page, per_page)
        if status != 200 or not items:
            break
        if incomplete:
            log.warning("%s page %d: incomplete_results=true", label, page)
        yield from _emit(items)
        if len(items) < per_page:
            break


def _fetch_combo(
    gh: GitHubClient,
    throttle: SearchThrottle,
    language: str,
    license_key: str,
    pushed_since: str,
    already_seen: Set[str],
    min_stars: int,
    biweekly_windows: List[Tuple[str, str]],
    pushed_end: str = "",
) -> Iterator[dict]:
    """
    Yield all repos for a single (language, license) pair.

    Three-level fallback strategy:
      1. Full date range, no explicit star cap (just min_stars).
         → if total_count < 1,000: paginate directly.
      2. Per static star bracket, full date range.
         → if total_count < 1,000: paginate directly.
      3. Per static star bracket, per 1-week window.
         → paginate; emit a warning if still capped (best effort).

    The first API call at each level serves double duty: it reveals
    total_count *and* provides the page-1 results, so no extra probe
    request is wasted.
    """
    base_label = f"lang={language} license={license_key}"

    # ------------------------------------------------------------------
    # Level 1 — try the full combo with no star subdivision
    # ------------------------------------------------------------------
    base_q = _build_query(language, license_key, pushed_since, min_stars, _STAR_HIGH_SENTINEL, pushed_end=pushed_end)
    total, items, status, inc = _fetch_page(gh, throttle, base_q, page=1)

    if status != 200:
        log.warning("%s: HTTP %d, skipping.", base_label, status)
        return
    if not items:
        log.debug("%s: 0 results.", base_label)
        return

    if total < 1000:
        log.debug("%s: total_count=%d, paginating directly.", base_label, total)
        if inc:
            log.warning("%s page 1: incomplete_results=true", base_label)
        yield from _paginate_query(gh, throttle, base_q, already_seen, items, base_label)
        return

    log.info("%s: total_count=%d >= 1000, splitting by star bracket.", base_label, total)

    # ------------------------------------------------------------------
    # Level 2 — per star bracket, full date range
    # ------------------------------------------------------------------
    for star_low, star_high in STAR_BRACKETS:
        effective_low = max(star_low, min_stars)
        if star_high < _STAR_HIGH_SENTINEL and star_high < min_stars:
            continue  # bracket entirely below the minimum

        high_str = "inf" if star_high >= _STAR_HIGH_SENTINEL else str(star_high)
        bracket_label = f"{base_label} stars={effective_low}..{high_str}"

        bracket_q = _build_query(language, license_key, pushed_since, effective_low, star_high, pushed_end=pushed_end)
        total_b, items_b, status_b, inc_b = _fetch_page(gh, throttle, bracket_q, page=1)

        if status_b != 200:
            log.warning("%s: HTTP %d, skipping bracket.", bracket_label, status_b)
            continue
        if not items_b:
            log.debug("%s: 0 results.", bracket_label)
            continue

        if total_b < 1000:
            log.debug("%s: total_count=%d, paginating directly.", bracket_label, total_b)
            if inc_b:
                log.warning("%s page 1: incomplete_results=true", bracket_label)
            yield from _paginate_query(gh, throttle, bracket_q, already_seen, items_b, bracket_label)
            continue

        log.info(
            "%s: total_count=%d >= 1000, splitting by 1-week window (%d windows).",
            bracket_label, total_b, len(biweekly_windows),
        )

        # --------------------------------------------------------------
        # Level 3 — per bracket, per 1-week window
        # --------------------------------------------------------------
        for win_start, win_end in biweekly_windows:
            win_label = f"{bracket_label} pushed={win_start}..{win_end}"
            win_q = _build_query(
                language, license_key, win_start, effective_low, star_high,
                pushed_end=win_end,
            )
            total_w, items_w, status_w, inc_w = _fetch_page(gh, throttle, win_q, page=1)

            if status_w != 200:
                log.warning("%s: HTTP %d, skipping window.", win_label, status_w)
                continue
            if not items_w:
                log.debug("%s: 0 results.", win_label)
                continue
            if total_w >= 1000:
                log.warning(
                    "%s: total_count=%d >= 1000 even after 1-week subdivision; "
                    "accepting up to 1,000 results for this window.",
                    win_label, total_w,
                )
            if inc_w:
                log.warning("%s page 1: incomplete_results=true", win_label)

            yield from _paginate_query(
                gh, throttle, win_q, already_seen, items_w, win_label,
            )



# ---------------------------------------------------------------------------
# Per-repo enrichment helpers
# ---------------------------------------------------------------------------

_LINK_PAGE_RE = re.compile(r'[?&]page=(\d+)')


def _parse_last_page(link_header: str) -> Optional[int]:
    """
    Extract the last page number from a GitHub Link header.

    GitHub paginates many endpoints and includes a ``Link`` header of the form:
        <url?page=2>; rel="next", <url?page=42>; rel="last"
    The page number in the ``rel="last"`` segment equals the total item count
    when the request used ``per_page=1``.
    """
    if not link_header:
        return None
    pages = [int(m.group(1)) for m in _LINK_PAGE_RE.finditer(link_header)]
    return max(pages) if pages else None


def _fetch_paginated_count(
    gh: GitHubClient,
    path: str,
    params: Optional[Dict] = None,
) -> Tuple[Optional[int], Optional[dict]]:
    """
    Fetch ``path`` with ``per_page=1`` and return ``(total_count, first_item)``.

    ``total_count`` is read from the ``Link`` header (last page number).
    When the result fits on a single page (no Link header), the body length is
    used instead.  Returns ``(None, None)`` on HTTP errors.
    """
    req_params = {"per_page": 1}
    if params:
        req_params.update(params)

    status, body, headers, err = gh.request_json_with_headers("GET", path, params=req_params)

    if status == 204:
        return (0, None)
    if status != 200:
        return (None, None)

    first_item: Optional[dict] = None
    if isinstance(body, list) and body:
        first_item = body[0]

    last_page = _parse_last_page(headers.get("Link", ""))
    if last_page is not None:
        return (last_page, first_item)

    # Single page — count is the actual number of items returned.
    count = len(body) if isinstance(body, list) else (1 if isinstance(body, dict) and body else 0)
    return (count, first_item)


# Fields populated by enrichment (used to detect whether a row needs enriching).
_ENRICH_FIELDS: List[str] = [
    "commits", "branches", "releases", "contributors", "languages", "lastCommitSHA",
]


def _needs_enrichment(row: Dict[str, str]) -> bool:
    """Return True if any enrichable field is still empty."""
    return any(not (row.get(f) or "").strip() for f in _ENRICH_FIELDS)


def _enrich_repo(gh: GitHubClient, repo_name: str) -> Dict[str, str]:
    """
    Fetch per-repo metadata not available from the search API.

    Makes up to 5 API calls:
      1. /contributors  → contributors count
      2. /commits       → commits count + lastCommitSHA (shared call)
      3. /branches      → branches count
      4. /releases      → releases count
      5. /languages     → semicolon-joined language names

    Returns a dict with the enriched field values (empty string on failure).
    """
    owner, name = repo_name.split("/", 1)
    base = f"/repos/{owner}/{name}"
    result: Dict[str, str] = {f: "" for f in _ENRICH_FIELDS}

    # 1. Contributors
    count, _ = _fetch_paginated_count(gh, f"{base}/contributors", params={"anon": "1"})
    if count is not None:
        result["contributors"] = str(count)

    # 2. Commits + lastCommitSHA (single request)
    count, first = _fetch_paginated_count(gh, f"{base}/commits")
    if count is not None:
        result["commits"] = str(count)
    if first and isinstance(first, dict):
        result["lastCommitSHA"] = first.get("sha", "")

    # 3. Branches
    count, _ = _fetch_paginated_count(gh, f"{base}/branches")
    if count is not None:
        result["branches"] = str(count)

    # 4. Releases
    count, _ = _fetch_paginated_count(gh, f"{base}/releases")
    if count is not None:
        result["releases"] = str(count)

    # 5. Languages — returns {"Python": 12345, ...} map directly (not paginated)
    status, body, err = gh.request_json("GET", f"{base}/languages")
    if status == 200 and isinstance(body, dict):
        result["languages"] = ";".join(body.keys())

    return result


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

_SLUG_OVERRIDES: Dict[str, str] = {
    "C#": "csharp",
    "C++": "cpp",
}


def _sanitize_name(s: str) -> str:
    """Convert a language or license string to a safe filename fragment."""
    if s in _SLUG_OVERRIDES:
        return _SLUG_OVERRIDES[s]
    return re.sub(r"[^a-zA-Z0-9]+", "_", s).strip("_").lower()


def _combo_csv_path(out_csv: str, language: str, license_key: str) -> str:
    """
    Derive a per-(language, license) CSV path from the main output path.

    Example: data/seart_csvs/github_search_results.csv + TypeScript + mit
             → data/seart_csvs/github_search_results_typescript_mit.csv
    """
    base, ext = os.path.splitext(out_csv)
    lang_slug = _sanitize_name(language)
    lic_slug = _sanitize_name(license_key)
    return f"{base}_{lang_slug}_{lic_slug}{ext}"


def _write_header(out_csv: str) -> None:
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SEART_COLUMNS)
        writer.writeheader()


def _append_row(out_csv: str, row: Dict[str, str]) -> None:
    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SEART_COLUMNS)
        writer.writerow(row)


def _rewrite_csv(out_csv: str, rows: List[Dict[str, str]]) -> None:
    """Atomically rewrite the CSV with updated rows."""
    out_dir = os.path.dirname(out_csv) or "."
    os.makedirs(out_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=out_dir, suffix=".csv")
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=SEART_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(tmp_path, out_csv)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _read_all_rows(out_csv: str) -> List[Dict[str, str]]:
    """Read all rows from the CSV into a list of dicts."""
    if not os.path.exists(out_csv):
        return []
    rows: List[Dict[str, str]] = []
    with open(out_csv, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(dict(row))
    return rows


def _load_already_fetched(out_csv: str) -> Set[str]:
    """Return set of full_names already written to the output CSV (for resume)."""
    if not os.path.exists(out_csv):
        return set()
    seen: Set[str] = set()
    try:
        with open(out_csv, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                name = (row.get("name") or "").strip()
                if name:
                    seen.add(name)
    except Exception:
        pass
    return seen


# ---------------------------------------------------------------------------
# Runtime / token-pool display helpers
# ---------------------------------------------------------------------------

def _fmt_elapsed(seconds: float) -> str:
    """Format a duration as h:mm:ss or m:ss."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


def _log_rate_limit(gh: GitHubClient) -> None:
    """Query /rate_limit and log the current quota for core and search APIs."""
    status, data, err = gh.request_json("GET", "/rate_limit")
    if status != 200:
        log.warning("Could not fetch rate-limit status (HTTP %d): %s", status, err)
        return

    resources = data.get("resources", {})
    core   = resources.get("core",   {})
    search = resources.get("search", {})

    def _reset_str(epoch: int) -> str:
        try:
            return dt.datetime.fromtimestamp(int(epoch), dt.timezone.utc).strftime("%H:%MZ")
        except Exception:
            return "?"

    log.info(
        "Rate limits — core: %d/%d (resets %s) | search: %d/%d (resets %s)",
        core.get("remaining", 0),   core.get("limit", 0),   _reset_str(core.get("reset", 0)),
        search.get("remaining", 0), search.get("limit", 0), _reset_str(search.get("reset", 0)),
    )

    stats = gh.pool.stats()
    if stats["token_count"] > 0:
        log.info(
            "Token pool — tokens: %d | total_requests: %d | core_remaining: %d",
            stats["token_count"], stats["total_requests"], stats["total_remaining"],
        )


def _postfix(written: int, pool: TokenPool, start_ts: float) -> str:
    """Build the tqdm postfix string shown after each combo completes."""
    stats = pool.stats()
    return (
        f"written={written}"
        f"  elapsed={_fmt_elapsed(time.time() - start_ts)}"
        f"  requests={stats['total_requests']}"
        f"  quota_remaining={stats['total_remaining']}"
    )


# ---------------------------------------------------------------------------
# Logging / CLI
# ---------------------------------------------------------------------------

def _setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=numeric,
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        stream=sys.stderr,
        force=True,
    )


def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Scrape GitHub repositories via GET /search/repositories and emit a "
            "SEART-compatible CSV for use with extract_skill_repos.py. "
            "Queries are split by (language, license) pair to stay under the "
            "1,000-result cap; star-bracket subdivision is applied automatically "
            "when a pair still hits the cap."
        )
    )
    p.add_argument(
        "--out-csv",
        default="data/seart_csvs/github_search_results.csv",
        help="Output CSV path (default: data/seart_csvs/github_search_results.csv)",
    )
    p.add_argument(
        "--min-stars",
        type=int,
        default=DEFAULT_MIN_STARS,
        help=f"Minimum star count (default: {DEFAULT_MIN_STARS})",
    )
    p.add_argument(
        "--pushed-since",
        default=DEFAULT_PUSHED_SINCE,
        help=f"Only include repos pushed since this date YYYY-MM-DD (default: {DEFAULT_PUSHED_SINCE})",
    )
    p.add_argument(
        "--end-date",
        default=None,
        help="Only include repos pushed up to this date YYYY-MM-DD (inclusive, default: today).",
    )
    p.add_argument(
        "--languages",
        nargs="+",
        default=DEFAULT_LANGUAGES,
        metavar="LANG",
        help=(
            "Languages to search (space-separated). "
            f"Default: {' '.join(DEFAULT_LANGUAGES)}"
        ),
    )
    p.add_argument(
        "--licenses",
        nargs="+",
        default=DEFAULT_LICENSES,
        metavar="LICENSE",
        help=(
            "License SPDX keys to search (space-separated). "
            f"Default: {' '.join(DEFAULT_LICENSES)}"
        ),
    )
    p.add_argument(
        "--resume",
        action="store_true",
        help="Append to an existing --out-csv, skipping repos already written.",
    )
    p.add_argument("--github-token", default="", help="Single GitHub PAT (overrides env).")
    p.add_argument(
        "--github-tokens",
        default="",
        help="Comma-separated GitHub PATs for multi-token rotation (overrides env).",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )

    # Enrichment controls
    enrich_group = p.add_argument_group("enrichment", "Per-repo API enrichment options")
    enrich_mode = enrich_group.add_mutually_exclusive_group()
    enrich_mode.add_argument(
        "--skip-enrich",
        action="store_true",
        help=(
            "Skip the per-repo enrichment phase after search. "
            "Produces a CSV with commits/branches/releases/contributors/languages empty."
        ),
    )
    enrich_mode.add_argument(
        "--enrich-only",
        action="store_true",
        help=(
            "Skip the search phase and only run enrichment on an existing --out-csv. "
            "Requires --out-csv to already exist."
        ),
    )
    enrich_group.add_argument(
        "--enrich-concurrency",
        type=int,
        default=4,
        metavar="N",
        help="Number of concurrent enrichment worker threads (default: 4).",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: List[str]) -> int:
    args = _parse_args(argv)
    _setup_logging(args.log_level)

    # Resolve tokens.
    raw_tokens = args.github_tokens.strip() or args.github_token.strip()
    if raw_tokens:
        tokens = [t.strip() for t in raw_tokens.split(",") if t.strip()]
    else:
        tokens = load_tokens_from_env()

    if not tokens:
        log.warning(
            "No GitHub token detected. Unauthenticated limit: 10 search req/min. "
            "Set GH_TOKENS / GH_TOKEN or pass --github-tokens / --github-token."
        )

    pool = TokenPool(tokens)
    # Use a separate SearchThrottle tuned for /search/repositories (30 req/min).
    repo_throttle = _repo_search_throttle()
    gh = GitHubClient(pool=pool)

    start_ts = time.time()

    # ------------------------------------------------------------------
    # Search phase (skipped when --enrich-only is set)
    # ------------------------------------------------------------------
    if not args.enrich_only:
        combos = [(lang, lic) for lang in args.languages for lic in args.licenses]

        # Build per-combo CSV paths and derive the set of already-fetched repos.
        # Resume reads from the combined file; combo files are (re)written fresh
        # unless they already exist with content (in which case they are appended).
        combo_csv: Dict[Tuple[str, str], str] = {
            (lang, lic): _combo_csv_path(args.out_csv, lang, lic)
            for lang, lic in combos
        }

        if args.resume and os.path.exists(args.out_csv):
            already_fetched = _load_already_fetched(args.out_csv)
            log.info("Resume: %d repos already in %s", len(already_fetched), args.out_csv)
            # Initialise combo files that don't yet exist.
            for path in combo_csv.values():
                if not os.path.exists(path) or os.path.getsize(path) == 0:
                    _write_header(path)
        else:
            already_fetched = set()
            _write_header(args.out_csv)
            for path in combo_csv.values():
                _write_header(path)

        # Parse and validate --end-date.
        end_date: dt.date | None = None
        pushed_end_str = ""
        if args.end_date:
            try:
                end_date = dt.date.fromisoformat(args.end_date)
            except ValueError:
                log.error("--end-date %r is not a valid YYYY-MM-DD date.", args.end_date)
                return 1
            pushed_end_str = end_date.isoformat()

        log.info(
            "Searching GitHub repositories | languages=%s | licenses=%s | "
            "min_stars=%d | pushed_since=%s | end_date=%s",
            args.languages, args.licenses, args.min_stars, args.pushed_since,
            pushed_end_str or "today",
        )
        log.info("Output CSV (combined): %s", args.out_csv)
        log.info("Per-combo CSVs written to: %s/", os.path.dirname(args.out_csv) or ".")

        # Compute 1-week windows once and log them so the user can see the plan.
        windows = _biweekly_windows(args.pushed_since, end_date=end_date)
        log.info(
            "1-week windows (%d): %s",
            len(windows),
            ", ".join(f"{s}..{e}" for s, e in windows),
        )

        # Show initial rate-limit quota so the user knows how much headroom they have.
        _log_rate_limit(gh)

        total_combos = len(combos)
        written = 0

        with logging_redirect_tqdm():
            with tqdm(total=total_combos, desc="Querying", unit="combo", file=sys.stderr) as pbar:
                for lang, lic in combos:
                    combo_path = combo_csv[(lang, lic)]
                    combo_written = 0

                    for repo in _fetch_combo(
                        gh, repo_throttle, lang, lic, args.pushed_since,
                        already_fetched, args.min_stars, windows,
                        pushed_end=pushed_end_str,
                    ):
                        row = _repo_to_seart_row(repo)
                        _append_row(args.out_csv, row)
                        _append_row(combo_path, row)
                        written += 1
                        combo_written += 1

                    pool_stats = pool.stats()
                    log.info(
                        "lang=%s license=%s: wrote %d repos to %s "
                        "| elapsed=%s requests=%d quota_remaining=%d",
                        lang, lic, combo_written, combo_path,
                        _fmt_elapsed(time.time() - start_ts),
                        pool_stats["total_requests"],
                        pool_stats["total_remaining"],
                    )
                    pbar.update(1)
                    pbar.set_postfix_str(_postfix(written, pool, start_ts), refresh=False)

        elapsed = time.time() - start_ts
        final_stats = pool.stats()
        log.info(
            "Search done | repos_written=%d | elapsed=%s | total_requests=%d | "
            "quota_remaining=%d | output=%s",
            written,
            _fmt_elapsed(elapsed),
            final_stats["total_requests"],
            final_stats["total_remaining"],
            args.out_csv,
        )
        _log_rate_limit(gh)

    # ------------------------------------------------------------------
    # Enrichment phase (skipped when --skip-enrich is set)
    # ------------------------------------------------------------------
    if args.skip_enrich:
        log.info("Skipping enrichment phase (--skip-enrich).")
        return 0

    if not os.path.exists(args.out_csv):
        log.error(
            "Enrichment phase: %s does not exist. "
            "Run without --enrich-only first to generate the search CSV.",
            args.out_csv,
        )
        return 1

    log.info("Enrichment phase: reading %s …", args.out_csv)
    all_rows = _read_all_rows(args.out_csv)
    pending_indices = [i for i, row in enumerate(all_rows) if _needs_enrichment(row)]

    if not pending_indices:
        log.info("Enrichment phase: all %d rows already enriched.", len(all_rows))
        return 0

    log.info(
        "Enrichment phase: %d/%d rows need enrichment | concurrency=%d",
        len(pending_indices), len(all_rows), args.enrich_concurrency,
    )
    _log_rate_limit(gh)

    enrich_start = time.time()
    enrich_updated = 0
    enrich_errors = 0
    checkpoint_every = 100  # rewrite CSV every N completed enrichments

    def _do_enrich(idx: int) -> Tuple[int, Dict[str, str]]:
        repo_name = all_rows[idx].get("name", "")
        enriched = _enrich_repo(gh, repo_name)
        return (idx, enriched)

    with logging_redirect_tqdm():
        with tqdm(
            total=len(pending_indices), desc="Enriching", unit="repo", file=sys.stderr
        ) as pbar:
            with ThreadPoolExecutor(max_workers=max(1, args.enrich_concurrency)) as executor:
                futures = {executor.submit(_do_enrich, idx): idx for idx in pending_indices}
                completed_since_checkpoint = 0

                for future in as_completed(futures):
                    try:
                        idx, enriched = future.result()
                        all_rows[idx].update(enriched)
                        enrich_updated += 1
                    except Exception as exc:
                        orig_idx = futures[future]
                        repo_name = all_rows[orig_idx].get("name", "?")
                        log.warning("Enrichment failed for %s: %s", repo_name, exc)
                        enrich_errors += 1

                    completed_since_checkpoint += 1
                    pbar.update(1)

                    if completed_since_checkpoint >= checkpoint_every:
                        _rewrite_csv(args.out_csv, all_rows)
                        completed_since_checkpoint = 0
                        pool_stats = pool.stats()
                        log.info(
                            "Enrichment checkpoint | enriched=%d errors=%d elapsed=%s "
                            "requests=%d quota_remaining=%d",
                            enrich_updated, enrich_errors,
                            _fmt_elapsed(time.time() - enrich_start),
                            pool_stats["total_requests"],
                            pool_stats["total_remaining"],
                        )

    # Final write to capture any remaining rows since the last checkpoint.
    _rewrite_csv(args.out_csv, all_rows)

    enrich_elapsed = time.time() - enrich_start
    final_stats = pool.stats()
    log.info(
        "Enrichment done | updated=%d errors=%d elapsed=%s "
        "total_requests=%d quota_remaining=%d output=%s",
        enrich_updated,
        enrich_errors,
        _fmt_elapsed(enrich_elapsed),
        final_stats["total_requests"],
        final_stats["total_remaining"],
        args.out_csv,
    )
    _log_rate_limit(gh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
