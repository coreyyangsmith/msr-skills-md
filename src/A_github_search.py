#!/usr/bin/env python3
"""
A_github_search.py

Alternative to SEART CSV ingestion: scrape GitHub repositories directly using
the GitHub REST API (GET /search/repositories) and emit a SEART-compatible CSV
that feeds into the existing pipeline (B_extract_skill_repos.py + C_generate_dataset.py).

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

Output CSV schema matches SEART exports so that B_extract_skill_repos.py and
C_generate_dataset.py can consume it unchanged.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import logging
import os
import re
import sys
import time
from typing import Dict, Iterator, List, Set, Tuple

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
# SEART CSV columns (mirrors B_extract_skill_repos.py)
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
    return f"{stars_q} language:{language} license:{license_key} {date_q}"


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
        "totalIssues":       str(repo.get("open_issues_count", "")),
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
# CSV I/O
# ---------------------------------------------------------------------------

def _sanitize_name(s: str) -> str:
    """Convert a language or license string to a safe filename fragment."""
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
            "SEART-compatible CSV for use with B_extract_skill_repos.py. "
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
    start_ts = time.time()

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
        "Done | repos_written=%d | elapsed=%s | total_requests=%d | quota_remaining=%d | output=%s",
        written,
        _fmt_elapsed(elapsed),
        final_stats["total_requests"],
        final_stats["total_remaining"],
        args.out_csv,
    )
    # Final rate-limit snapshot so the user can see exact reset times.
    _log_rate_limit(gh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
