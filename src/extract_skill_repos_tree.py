#!/usr/bin/env python3
"""
extract_skill_repos_tree.py

Tree-first alternative to extract_skill_repos.py.

This scanner preserves the existing Stage 2 CSV schema and split-output
contract, but avoids GitHub Code Search. It fetches repository git trees via
the core REST API, detects SKILL.md and companion files locally, and emits rows
compatible with downstream Stage 2.5 and Stage 3 scripts.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote

from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from extract_skill_repos import (
    ACF_CONTENTS_CHECKS,
    OUTPUT_COLUMNS,
    RepoSource,
    ScanResult,
    append_result,
    check_rate_limit,
    classify_error,
    ingest_seart_csvs,
    load_already_scanned,
    load_blacklist,
    result_category,
    resolve_commit_sha,
    split_csv_paths,
    utc_now_iso,
    validate_existing_output_header,
    write_header_if_needed,
    write_shortlist,
)
from github_client import GitHubClient, TokenPool, load_tokens_from_env

log = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = "outputs/cache/tree_scan"

_README_EXTENSIONS = {
    "",
    ".md",
    ".markdown",
    ".rst",
    ".txt",
    ".adoc",
    ".asciidoc",
    ".org",
}


@dataclasses.dataclass
class FetchTreeResult:
    tree: List[Dict[str, Any]]
    status: int
    error: str
    scan_method: str
    truncated: bool = False


@dataclasses.dataclass
class TreeDetection:
    best_skill: Optional[Dict[str, Any]]
    readiness_flags: Dict[str, str]
    acf_flags: Dict[str, str]


def _setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=numeric,
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        stream=sys.stderr,
        force=True,
    )


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Tree-first Stage 2 scanner for SKILL.md. This preserves the "
            "extract_skill_repos.py CSV schema while using GitHub git-tree "
            "API calls instead of Code Search."
        )
    )
    parser.add_argument("--seart-dir", required=True, help="Directory containing SEART CSV exports")
    parser.add_argument("--out-csv", required=True, help="Output results CSV path")
    parser.add_argument("--shortlist-csv", default="", help="Optional shortlist CSV path (found=true only)")
    parser.add_argument("--match-name", default="SKILL.md", help="Filename to detect in git trees")
    parser.add_argument("--max-repos", type=int, default=0, help="Limit repos scanned (0 means no limit)")
    parser.add_argument("--blacklist", default="blacklist.txt", help="Path to blacklist file (owner/repo per line)")
    parser.add_argument("--resume", action="store_true", help="Skip repos already present in --out-csv")
    parser.add_argument(
        "--include-negative-results",
        action="store_true",
        help="Compatibility no-op: every row is always written to --out-csv.",
    )
    parser.add_argument("--concurrency", type=int, default=4, help="Worker threads")
    parser.add_argument("--github-token", default="", help="Single GitHub token; overrides env")
    parser.add_argument("--github-tokens", default="", help="Comma-separated GitHub tokens; overrides env")
    parser.add_argument(
        "--cache-dir",
        default=DEFAULT_CACHE_DIR,
        help=f"Directory for cached tree responses (default: {DEFAULT_CACHE_DIR})",
    )
    parser.add_argument(
        "--cache-mode",
        choices=["read-write", "read-only", "off"],
        default="read-write",
        help="Tree cache behavior (default: read-write)",
    )
    parser.add_argument(
        "--fallback",
        choices=["none", "walk-tree"],
        default="walk-tree",
        help="Fallback when recursive tree responses are truncated (default: walk-tree)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser.parse_args(argv)


def _resolve_tokens(args: argparse.Namespace) -> list[str]:
    raw_tokens = args.github_tokens.strip() or args.github_token.strip()
    if raw_tokens:
        return [token.strip() for token in raw_tokens.split(",") if token.strip()]
    return load_tokens_from_env()


def _repo_cache_path(cache_dir: str, repo: str, ref: str, mode: str) -> Path:
    key = hashlib.sha256(f"{repo}@{ref}:{mode}".encode("utf-8")).hexdigest()
    owner, name = repo.split("/", 1)
    safe_repo = f"{owner}__{name}".replace("\\", "_").replace("/", "_")
    return Path(cache_dir) / safe_repo / f"{key}.json"


def _read_cached_tree(cache_dir: str, repo: str, ref: str, mode: str) -> Optional[FetchTreeResult]:
    if not cache_dir:
        return None
    path = _repo_cache_path(cache_dir, repo, ref, mode)
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        log.debug("Ignoring unreadable tree cache %s: %s", path, exc)
        return None
    tree = payload.get("tree")
    if not isinstance(tree, list):
        return None
    return FetchTreeResult(
        tree=tree,
        status=int(payload.get("status", 200) or 200),
        error=str(payload.get("error", "") or ""),
        scan_method=str(payload.get("scan_method", mode) or mode),
        truncated=bool(payload.get("truncated", False)),
    )


def _write_cached_tree(
    cache_dir: str,
    repo: str,
    ref: str,
    mode: str,
    result: FetchTreeResult,
    etag: str = "",
) -> None:
    if not cache_dir or result.error:
        return
    path = _repo_cache_path(cache_dir, repo, ref, mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "repo": repo,
        "ref": ref,
        "status": result.status,
        "error": result.error,
        "scan_method": result.scan_method,
        "truncated": result.truncated,
        "etag": etag,
        "fetched_at_utc": utc_now_iso(),
        "tree": result.tree,
    }
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    os.replace(tmp_path, path)


def _combine_path(prefix: str, path: str) -> str:
    if not prefix:
        return path
    if not path:
        return prefix
    return f"{prefix}/{path}"


def _walk_tree_recursive(
    gh: GitHubClient,
    repo: str,
    tree_sha: str,
    prefix: str = "",
) -> Tuple[List[Dict[str, Any]], int, str]:
    owner, name = repo.split("/", 1)
    sha_quoted = quote(tree_sha, safe="")
    status, data, _headers, err = gh.request_json_with_headers(
        "GET",
        f"/repos/{owner}/{name}/git/trees/{sha_quoted}",
    )
    if status != 200 or not isinstance(data, dict):
        return [], status, err or f"http_{status}"

    out: List[Dict[str, Any]] = []
    for item in data.get("tree") or []:
        item_type = item.get("type")
        item_path = str(item.get("path") or "")
        full_path = _combine_path(prefix, item_path)
        if item_type == "blob":
            copied = dict(item)
            copied["path"] = full_path
            out.append(copied)
        elif item_type == "tree" and item.get("sha"):
            child_items, child_status, child_err = _walk_tree_recursive(
                gh,
                repo,
                str(item["sha"]),
                full_path,
            )
            if child_err:
                return [], child_status, child_err
            out.extend(child_items)
    return out, 200, ""


def _fetch_recursive_tree(
    gh: GitHubClient,
    repo: str,
    ref: str,
) -> Tuple[FetchTreeResult, str]:
    owner, name = repo.split("/", 1)
    ref_quoted = quote(ref, safe="")
    status, data, headers, err = gh.request_json_with_headers(
        "GET",
        f"/repos/{owner}/{name}/git/trees/{ref_quoted}",
        params={"recursive": "1"},
    )
    if status != 200 or not isinstance(data, dict):
        return FetchTreeResult([], status, err or f"http_{status}", "tree_recursive"), ""
    tree = data.get("tree") or []
    if not isinstance(tree, list):
        return FetchTreeResult([], status, "unexpected_tree_response", "tree_recursive"), ""
    return (
        FetchTreeResult(
            tree=tree,
            status=status,
            error="",
            scan_method="tree_recursive",
            truncated=bool(data.get("truncated")),
        ),
        headers.get("ETag", ""),
    )


def fetch_repo_tree(
    gh: GitHubClient,
    repo: str,
    ref: str,
    cache_dir: str = DEFAULT_CACHE_DIR,
    cache_mode: str = "read-write",
    fallback: str = "walk-tree",
) -> FetchTreeResult:
    if cache_mode != "off":
        cached = _read_cached_tree(cache_dir, repo, ref, "tree_recursive")
        if cached:
            return cached
        cached_walk = _read_cached_tree(cache_dir, repo, ref, "tree_walk")
        if cached_walk:
            return cached_walk
        if cache_mode == "read-only":
            return FetchTreeResult([], 0, "cache_miss", "tree_recursive")

    recursive_result, etag = _fetch_recursive_tree(gh, repo, ref)
    if recursive_result.error:
        return recursive_result
    if not recursive_result.truncated:
        if cache_mode == "read-write":
            _write_cached_tree(cache_dir, repo, ref, "tree_recursive", recursive_result, etag)
        return recursive_result

    if fallback == "none":
        return FetchTreeResult(
            [],
            recursive_result.status,
            "tree_truncated",
            "tree_recursive",
            truncated=True,
        )

    tree, status, err = _walk_tree_recursive(gh, repo, ref)
    if err:
        return FetchTreeResult([], status, err, "tree_walk", truncated=True)
    walk_result = FetchTreeResult(tree, status, "", "tree_walk", truncated=True)
    if cache_mode == "read-write":
        _write_cached_tree(cache_dir, repo, ref, "tree_walk", walk_result, etag)
    return walk_result


def _basename(path: str) -> str:
    return path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def _lower_path(path: str) -> str:
    return path.replace("\\", "/").lstrip("/").lower()


def _is_readme(path: str) -> bool:
    lower = _lower_path(path)
    parts = lower.split("/")
    if len(parts) > 2 or (len(parts) == 2 and parts[0] != ".github"):
        return False
    name = parts[-1]
    stem, ext = os.path.splitext(name)
    return stem == "readme" and ext in _README_EXTENSIONS


def _is_contributing(path: str) -> bool:
    lower = _lower_path(path)
    parts = lower.split("/")
    if len(parts) > 2 or (len(parts) == 2 and parts[0] != ".github"):
        return False
    return os.path.splitext(parts[-1])[0] == "contributing"


def _is_security(path: str) -> bool:
    lower = _lower_path(path)
    parts = lower.split("/")
    if len(parts) > 2 or (len(parts) == 2 and parts[0] != ".github"):
        return False
    return os.path.splitext(parts[-1])[0] == "security"


def _is_code_of_conduct(path: str) -> bool:
    lower = _lower_path(path)
    parts = lower.split("/")
    if len(parts) > 2 or (len(parts) == 2 and parts[0] != ".github"):
        return False
    stem = os.path.splitext(parts[-1])[0]
    normalized = stem.replace("-", "_")
    return normalized == "code_of_conduct"


def _detect_readiness_flags(paths: List[str]) -> Dict[str, str]:
    return {
        "has_README": "1" if any(_is_readme(path) for path in paths) else "0",
        "has_CONTRIBUTING": "1" if any(_is_contributing(path) for path in paths) else "0",
        "has_SECURITY": "1" if any(_is_security(path) for path in paths) else "0",
        "has_CODE_OF_CONDUCT": "1" if any(_is_code_of_conduct(path) for path in paths) else "0",
    }


def _detect_acf_flags(paths: List[str]) -> Dict[str, str]:
    normalized_paths = {_lower_path(path) for path in paths}
    basenames = {_basename(path).lower() for path in paths}
    flags: Dict[str, str] = {}
    for target_path, attr in ACF_CONTENTS_CHECKS:
        clean = target_path.lstrip("/").lower()
        base = clean.rsplit("/", 1)[-1]
        flags[attr] = "1" if clean in normalized_paths or base in basenames else "0"
    return flags


def scan_tree_entries(tree_items: List[Dict[str, Any]], match_name: str) -> TreeDetection:
    blobs = [item for item in tree_items if item.get("type") == "blob" and item.get("path")]
    paths = [str(item.get("path") or "") for item in blobs]
    skill_items = [
        item
        for item in blobs
        if _basename(str(item.get("path") or "")) == match_name
    ]

    best_skill: Optional[Dict[str, Any]] = None
    if skill_items:
        best_skill = sorted(
            skill_items,
            key=lambda item: (len(str(item.get("path") or "")), str(item.get("path") or "")),
        )[0]

    return TreeDetection(
        best_skill=best_skill,
        readiness_flags=_detect_readiness_flags(paths),
        acf_flags=_detect_acf_flags(paths),
    )


def _new_result(repo_src: RepoSource, match_name: str) -> ScanResult:
    sd = repo_src.seart_data
    default_branch = sd.get("defaultBranch") or ""
    return ScanResult(
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
        scan_method="tree_recursive",
        http_status="",
        error_type="none",
        error_message="",
        acf_error_type="",
        acf_error_message="",
        scanned_at_utc=utc_now_iso(),
        stars=sd.get("stargazers") or "",
        fork=sd.get("isFork") or "",
        archived=sd.get("isArchived") or "",
        seart_data=dict(sd),
    )


def scan_one_repo_tree(
    gh: GitHubClient,
    repo_src: RepoSource,
    match_name: str,
    cache_dir: str = DEFAULT_CACHE_DIR,
    cache_mode: str = "read-write",
    fallback: str = "walk-tree",
) -> ScanResult:
    res = _new_result(repo_src, match_name)
    ref = res.default_branch or "HEAD"
    resolved_sha = resolve_commit_sha(gh, repo_src.repo, ref)
    tree_ref = resolved_sha or ref

    tree_result = fetch_repo_tree(
        gh,
        repo_src.repo,
        tree_ref,
        cache_dir=cache_dir,
        cache_mode=cache_mode,
        fallback=fallback,
    )
    res.scan_method = tree_result.scan_method
    res.http_status = str(tree_result.status) if tree_result.status else ""

    if tree_result.error:
        if tree_result.error == "tree_truncated":
            res.error_type = "other"
        else:
            res.error_type = classify_error(tree_result.status, tree_result.error)
        res.error_message = tree_result.error
        return res

    detected = scan_tree_entries(tree_result.tree, match_name)
    for attr, value in detected.readiness_flags.items():
        setattr(res, attr, value)
    for attr, value in detected.acf_flags.items():
        setattr(res, attr, value)

    if not detected.best_skill:
        return res

    skill_path = str(detected.best_skill.get("path") or "")
    res.found = True
    res.match_path = "/" + skill_path.lstrip("/")
    res.match_sha = str(detected.best_skill.get("sha") or "")
    size = detected.best_skill.get("size", "")
    res.match_size_bytes = "" if size is None else str(size)
    res.commit_sha = resolved_sha
    res.acf_ref = resolved_sha or ref
    res.match_url = f"https://github.com/{repo_src.repo}/blob/{res.acf_ref}/{skill_path}"
    res.error_type = "none"
    res.error_message = ""
    return res


def _fmt_elapsed(seconds: float) -> str:
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    _setup_logging(args.log_level)

    tokens = _resolve_tokens(args)
    if not tokens:
        log.warning(
            "No GitHub token detected. Unauthenticated core REST limits are low. "
            "Set GH_TOKENS / GH_TOKEN or pass --github-tokens / --github-token."
        )

    gh = GitHubClient(pool=TokenPool(tokens))
    resources = check_rate_limit(gh)

    log.info("Ingesting SEART CSVs from: %s", args.seart_dir)
    repos, ingest_errors = ingest_seart_csvs(args.seart_dir)
    for err in ingest_errors:
        log.warning("Ingest: %s", err)
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
    repos_to_scan = [
        repo_src
        for repo_src in repos
        if repo_src.repo not in already and repo_src.repo not in blacklist
    ]

    found_csv, not_found_csv, errors_csv, filtered_csv = split_csv_paths(args.out_csv)
    for path in (args.out_csv, found_csv, not_found_csv, errors_csv, filtered_csv):
        write_header_if_needed(path)

    if not repos_to_scan:
        log.info("Nothing to scan.")
        if args.shortlist_csv:
            write_shortlist(args.out_csv, args.shortlist_csv)
        return 0

    core_remaining = resources.get("core", {}).get("remaining", 0) if resources else 0
    if core_remaining and len(repos_to_scan) > core_remaining:
        log.warning(
            "Estimated tree requests needed (%d+) exceeds current core quota remaining (%d). "
            "TokenPool will wait and resume automatically if quota is exhausted.",
            len(repos_to_scan),
            core_remaining,
        )

    log.info(
        "Tree-first scanning %d repositories | concurrency=%d | match=%s | cache=%s (%s) | fallback=%s",
        len(repos_to_scan),
        args.concurrency,
        args.match_name,
        args.cache_dir,
        args.cache_mode,
        args.fallback,
    )

    counts = {"found": 0, "not_found": 0, "filtered": 0, "rate_limited": 0, "errors": 0}
    error_type_counts: Dict[str, int] = {}
    scan_start = time.time()

    with ThreadPoolExecutor(max_workers=max(1, int(args.concurrency))) as executor:
        futures = {
            executor.submit(
                scan_one_repo_tree,
                gh,
                repo_src,
                args.match_name,
                args.cache_dir,
                args.cache_mode,
                args.fallback,
            ): repo_src.repo
            for repo_src in repos_to_scan
        }

        with logging_redirect_tqdm():
            with tqdm(total=len(futures), desc="Tree scanning", unit="repo", file=sys.stderr) as pbar:
                for future in as_completed(futures):
                    repo = futures[future]
                    try:
                        result = future.result()
                    except Exception as exc:
                        log.exception("Unexpected error scanning %s", repo)
                        result = ScanResult(
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
                            scan_method="tree_recursive",
                            http_status="0",
                            error_type="other",
                            error_message=f"exception: {exc}",
                            acf_error_type="",
                            acf_error_message="",
                            scanned_at_utc=utc_now_iso(),
                            stars="",
                            fork="",
                            archived="",
                            seart_data={},
                        )

                    category = result_category(result)
                    if category == "found":
                        counts["found"] += 1
                    elif category == "not_found":
                        counts["not_found"] += 1
                    elif category == "filtered":
                        counts["filtered"] += 1
                    elif result.error_type == "rate_limited":
                        counts["rate_limited"] += 1
                    else:
                        counts["errors"] += 1
                    error_type_counts[result.error_type] = error_type_counts.get(result.error_type, 0) + 1

                    append_result(args.out_csv, result)
                    if category == "found":
                        append_result(found_csv, result)
                    elif category == "not_found":
                        append_result(not_found_csv, result)
                    elif category == "filtered":
                        append_result(filtered_csv, result)
                    else:
                        append_result(errors_csv, result)

                    pbar.update(1)
                    pbar.set_postfix_str(
                        f"found={counts['found']}"
                        f"  not_found={counts['not_found']}"
                        f"  filtered={counts['filtered']}"
                        f"  rate_limited={counts['rate_limited']}"
                        f"  errors={counts['errors']}",
                        refresh=False,
                    )

    if args.shortlist_csv:
        write_shortlist(args.out_csv, args.shortlist_csv)

    scanned = sum(counts.values())
    elapsed = time.time() - scan_start
    found_pct = 100.0 * counts["found"] / scanned if scanned else 0.0
    log.info(
        "Tree scan complete | elapsed=%s | scanned=%d | found=%d (%.1f%%) | "
        "not_found=%d | filtered=%d | rate_limited=%d | errors=%d",
        _fmt_elapsed(elapsed),
        scanned,
        counts["found"],
        found_pct,
        counts["not_found"],
        counts["filtered"],
        counts["rate_limited"],
        counts["errors"],
    )
    log.info("Error type breakdown: %s", dict(sorted(error_type_counts.items())))
    log.info("Output | all=%s", args.out_csv)
    log.info("Output | found=%s", found_csv)
    log.info("Output | not_found=%s", not_found_csv)
    log.info("Output | errors=%s", errors_csv)
    log.info("Output | filtered=%s", filtered_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
