#!/usr/bin/env python3
"""
generate_dataset.py

Re-processes repositories from extract_skill_repos.py output to:
1. Re-query full GitHub tree for all SKILL.md instances.
2. Compute metrics for skill subfolders (references, assets, scripts, other).
3. Output full_skills_instances.csv with calculated metrics.
4. Download the full parent folder of each SKILL.md into raw_data/.
"""

from __future__ import annotations

import argparse
import base64
import csv
import dataclasses
import datetime as dt
import json
import logging
import os
import pathlib
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import quote

from github_client import GitHubClient, TokenPool, load_tokens_from_env
from filters import REPO_NAME_FILTER_WORDS, load_blacklist, repo_name_contains_filter_word

log = logging.getLogger(__name__)

# All columns present in a SEART CSV export (mirrors extract_skill_repos.py).
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

@dataclasses.dataclass
class SkillMetrics:
    total_files: int = 0
    references_count: int = 0
    assets_count: int = 0
    scripts_count: int = 0
    other_count: int = 0


@dataclasses.dataclass
class SkillInstance:
    skill_path: str
    parent_folder: str
    metrics: SkillMetrics
    files: List[Dict[str, Any]] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class SkillInstanceRow:
    """One row per SKILL.md instance found in a repository."""
    repo: str
    default_branch: str
    stars: str
    fork: str
    archived: str
    html_url: str
    skill_path: str = ""
    skill_parent_folder: str = ""
    total_files: int = 0
    has_references: int = 0
    references_file_count: int = 0
    has_assets: int = 0
    assets_file_count: int = 0
    has_scripts: int = 0
    scripts_file_count: int = 0
    has_other: int = 0
    other_file_count: int = 0
    scanned_at_utc: str = ""
    has_README: int = 0
    has_CONTRIBUTING: int = 0
    has_SECURITY: int = 0
    has_CODE_OF_CONDUCT: int = 0
    has_CLAUDE: int = 0
    has_AGENTS: int = 0
    has_COPILOT: int = 0
    # Original SEART columns carried through from the input CSV.
    seart_data: Dict[str, str] = dataclasses.field(default_factory=dict)


# Ordered list of dataset-specific output columns (everything except seart_data).
_DATASET_COLUMNS: List[str] = [
    f.name for f in dataclasses.fields(SkillInstanceRow) if f.name != "seart_data"
]

# Full output schema: dataset columns first, then all SEART columns.
OUTPUT_COLUMNS: List[str] = _DATASET_COLUMNS + SEART_COLUMNS


# ----------------------------
# Logic
# ----------------------------

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def row_flag_to_int(row: Dict[str, str], column: str) -> int:
    return 1 if str(row.get(column, "")).strip().lower() in {"1", "true", "yes"} else 0


def fetch_repo_tree(gh: GitHubClient, repo: str, branch: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Fetch the full recursive tree for a repo branch.
    Returns (tree_items, error_message).
    """
    owner, name = repo.split("/", 1)
    # The API is /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1
    ref_quoted = quote(branch, safe="")
    status, data, err = gh.request_json("GET", f"/repos/{owner}/{name}/git/trees/{ref_quoted}", params={"recursive": "1"})
    
    if status == 404 or status == 409: # 409 happens for empty repositories
        return [], "tree_not_found"
    if status == 403 or status == 429:
        # Should not reach here typically due to retry, but if max_retries hit
        return [], "rate_limited"
    if status != 200 or not isinstance(data, dict):
        return [], err or f"http_{status}"

    if data.get("truncated"):
        # A partial tree can silently produce skill_count: 0 false negatives for
        # large repos.  Treat as an error so the repo stays retryable.
        log.warning("Tree for %s is truncated; treating as an error.", repo)
        return [], "tree_truncated"

    tree = data.get("tree", [])
    return tree, ""


def find_skill_instances(tree_items: List[Dict[str, Any]], match_name: str) -> List[SkillInstance]:
    """
    Find all files matching match_name and group files by their parent directories.
    """
    # Find all SKILL.md paths
    skill_paths = []
    for item in tree_items:
        if item.get("type") == "blob":
            path = item.get("path", "")
            name = os.path.basename(path)
            if name == match_name:
                skill_paths.append(path)

    instances = []
    for sp in skill_paths:
        parent = os.path.dirname(sp)
        # Empty parent means it's in the root, we'll represent root as ""
        
        prefix = parent + "/" if parent else ""
        
        _SKILL_SUBDIRS = {"references", "assets", "scripts"}

        files_in_skill = []
        for item in tree_items:
            if item.get("type") == "blob":
                item_path = item.get("path", "")
                if parent == "":
                    # SKILL.md is at the repo root. Downloading the entire repo
                    # tree blob-by-blob would stall on large repos, so we limit
                    # to direct root siblings and the standard skill subdirs.
                    parts = item_path.split("/")
                    if len(parts) == 1 or (len(parts) >= 2 and parts[0] in _SKILL_SUBDIRS):
                        files_in_skill.append(item)
                elif item_path.startswith(prefix):
                    files_in_skill.append(item)
        
        metrics = compute_skill_metrics(parent, files_in_skill, match_name)
        instances.append(SkillInstance(
            skill_path=sp,
            parent_folder=parent,
            metrics=metrics,
            files=files_in_skill
        ))

    # Sort instances deterministically
    instances.sort(key=lambda x: x.skill_path)
    return instances


def compute_skill_metrics(parent_folder: str, files: List[Dict[str, Any]], match_name: str) -> SkillMetrics:
    """
    Compute metrics for a single skill based on its files.
    Files belong to subfolders: references/, assets/, scripts/, other.
    """
    m = SkillMetrics(total_files=len(files))
    
    prefix = parent_folder + "/" if parent_folder else ""
    
    for f in files:
        path = f.get("path", "")
        # Remove parent prefix to get relative path within the skill folder
        if path.startswith(prefix):
            rel_path = path[len(prefix):]
        else:
            rel_path = path
            
        if rel_path == match_name:
            continue
            
        parts = rel_path.split("/")
        if len(parts) > 1:
            top_dir = parts[0]
            if top_dir == "references":
                m.references_count += 1
            elif top_dir == "assets":
                m.assets_count += 1
            elif top_dir == "scripts":
                m.scripts_count += 1
            else:
                m.other_count += 1
        else:
            m.other_count += 1
            
    return m


_WINDOWS_INVALID_CHARS = r'\/:*?"<>|'
_WINDOWS_INVALID_RE = re.compile(r'[\\/:*?"<>|]')


def sanitize_path_component(name: str) -> str:
    """Replace characters that are invalid in Windows file/directory names."""
    return _WINDOWS_INVALID_RE.sub("_", name)


def sanitize_relative_path(rel_path: str) -> str:
    """Sanitize each component of a forward-slash-separated relative path."""
    parts = rel_path.replace("\\", "/").split("/")
    return os.path.join(*[sanitize_path_component(p) for p in parts if p])


def download_blob(gh: GitHubClient, repo: str, sha: str) -> Tuple[Optional[bytes], str]:
    """
    Download a git blob by its SHA.
    """
    owner, name = repo.split("/", 1)
    status, data, err = gh.request_json("GET", f"/repos/{owner}/{name}/git/blobs/{sha}")
    if status == 200 and isinstance(data, dict):
        content_b64 = data.get("content", "")
        encoding = data.get("encoding", "")
        if encoding == "base64":
            try:
                # GitHub base64 can have newlines
                return base64.b64decode(content_b64), ""
            except Exception as e:
                return None, f"b64decode_error: {e}"
        else:
            return None, f"unsupported_encoding: {encoding}"
    return None, err or f"http_{status}"


def download_skill_files(gh: GitHubClient, repo: str, skill: SkillInstance, repo_dir: str) -> List[str]:
    """
    Download all files for a skill instance into repo_dir.
    Returns list of errors if any.
    """
    errors = []
    
    prefix = skill.parent_folder + "/" if skill.parent_folder else ""
    
    for f in skill.files:
        path = f.get("path", "")
        sha = f.get("sha", "")
        
        if path.startswith(prefix):
            rel_path = path[len(prefix):]
        else:
            rel_path = path

        # Determine local path: repo_dir/<full_skill_folder_path>/rel_path
        # Use the full parent_folder path (not just its basename) so that skills
        # nested at different depths with the same leaf name (e.g. Packs/A/src and
        # Packs/B/src) are stored in separate directories and don't overwrite each
        # other.  Each path component is sanitized individually for Windows.
        if skill.parent_folder:
            folder_path = sanitize_relative_path(skill.parent_folder)
        else:
            folder_path = "root"
        local_path = os.path.join(repo_dir, folder_path, sanitize_relative_path(rel_path))
        
        # Ensure dir exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        
        # Only download if we have a SHA and it's a blob
        if sha:
            # Check if file already exists and has size
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                continue
                
            content, err = download_blob(gh, repo, sha)
            if content is not None:
                try:
                    with open(local_path, "wb") as out_f:
                        out_f.write(content)
                except Exception as e:
                    errors.append(f"failed to write {rel_path}: {e}")
            else:
                errors.append(f"failed to download {rel_path} (sha {sha}): {err}")
                
    return errors


def process_repo(
    gh: GitHubClient,
    row: Dict[str, str],
    raw_data_dir: str,
    match_name: str,
) -> Tuple[List[SkillInstanceRow], List[str]]:
    """
    Process a single repository.
    Returns (list of one SkillInstanceRow per SKILL.md found, list_of_errors).
    """
    repo = row["repo"]
    branch = row.get("default_branch") or "main"
    # Prefer the pinned commit SHA recorded by stage 2 to avoid drift from
    # re-querying a moving branch tip. Fall back to branch name for old CSVs
    # that pre-date this field.
    tree_ref = row.get("commit_sha") or branch

    repo_safe = repo.replace("/", "__")

    # Store each repo under a language-specific subfolder, e.g. raw_data/Python/owner__repo/
    language = (row.get("mainLanguage") or "").strip() or "unknown"
    language_safe = language.replace("/", "_").replace("\\", "_")
    repo_dir = os.path.join(raw_data_dir, language_safe, repo_safe)
    metadata_path = os.path.join(repo_dir, "metadata.json")

    # Check if already processed via metadata
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            skill_count = int(metadata.get("skill_count", 0) or 0)
            # Old zero-skill metadata should be retried rather than becoming sticky.
            if skill_count > 0:
                # Also verify that the number of SKILL.md files on disk matches
                # the recorded skill_count.  A mismatch means a prior run used the
                # basename-only folder scheme and some files collided; re-process so
                # the full-path layout is written correctly.
                disk_count = sum(
                    1 for p in pathlib.Path(repo_dir).rglob("SKILL.md")
                    if p.is_file() and p.name == "SKILL.md"
                )
                if disk_count >= skill_count:
                    return [], []
                log.info(
                    "[%s] Disk has %d SKILL.md file(s) but metadata records %d; re-downloading.",
                    repo, disk_count, skill_count,
                )
        except Exception:
            pass  # corrupted metadata, re-process

    tree_items, tree_err = fetch_repo_tree(gh, repo, tree_ref)
    if tree_err:
        return [], [f"Tree fetch failed: {tree_err}"]

    skills = find_skill_instances(tree_items, match_name)

    # Detect ACF files anywhere in the repo using case-insensitive basename matching.
    # First match per target wins (covers CLAUDE.md, claude.md, Claude.md, etc.).
    _ACF_TARGETS: Dict[str, str] = {
        "claude.md": "has_CLAUDE",
        "agents.md": "has_AGENTS",
        "copilot-instructions.md": "has_COPILOT",
    }
    acf_found: List[Tuple[str, Dict[str, Any], str]] = []  # (path, tree_item, attr)
    _acf_matched_attrs: Set[str] = set()
    for item in tree_items:
        if item.get("type") == "blob":
            item_path = item.get("path", "")
            attr = _ACF_TARGETS.get(os.path.basename(item_path).lower())
            if attr and attr not in _acf_matched_attrs:
                acf_found.append((item_path, item, attr))
                _acf_matched_attrs.add(attr)

    # Repo-level ACF flags shared across all skill rows for this repo.
    acf_flags: Dict[str, int] = {attr: 0 for attr in _ACF_TARGETS.values()}
    for _, _, attr in acf_found:
        acf_flags[attr] = 1

    # Carry through every original SEART column from the input row.
    seart_data = {col: (row.get(col) or "") for col in SEART_COLUMNS}

    stars = row.get("stars", "")
    scanned_at = utc_now_iso()
    maintainer_flags = {
        "has_README": row_flag_to_int(row, "has_README"),
        "has_CONTRIBUTING": row_flag_to_int(row, "has_CONTRIBUTING"),
        "has_SECURITY": row_flag_to_int(row, "has_SECURITY"),
        "has_CODE_OF_CONDUCT": row_flag_to_int(row, "has_CODE_OF_CONDUCT"),
    }

    # Build one output row per skill instance.
    skill_rows: List[SkillInstanceRow] = []
    for s in skills:
        m = s.metrics
        skill_rows.append(SkillInstanceRow(
            repo=repo,
            default_branch=branch,
            stars=stars,
            fork=row.get("fork", ""),
            archived=row.get("archived", ""),
            html_url=f"https://github.com/{repo}",
            skill_path=s.skill_path,
            skill_parent_folder=s.parent_folder,
            total_files=m.total_files,
            has_references=1 if m.references_count else 0,
            references_file_count=m.references_count,
            has_assets=1 if m.assets_count else 0,
            assets_file_count=m.assets_count,
            has_scripts=1 if m.scripts_count else 0,
            scripts_file_count=m.scripts_count,
            has_other=1 if m.other_count else 0,
            other_file_count=m.other_count,
            scanned_at_utc=scanned_at,
            has_README=maintainer_flags["has_README"],
            has_CONTRIBUTING=maintainer_flags["has_CONTRIBUTING"],
            has_SECURITY=maintainer_flags["has_SECURITY"],
            has_CODE_OF_CONDUCT=maintainer_flags["has_CODE_OF_CONDUCT"],
            has_CLAUDE=acf_flags["has_CLAUDE"],
            has_AGENTS=acf_flags["has_AGENTS"],
            has_COPILOT=acf_flags["has_COPILOT"],
            seart_data=seart_data,
        ))

    # When the tree was fetched successfully but no matching files exist, do NOT
    # write metadata.json — doing so would permanently hide the repo from future
    # --resume runs, turning a false negative into a permanent miss.
    if not skills:
        return [], ["zero_skills_found"]

    # Download SKILL.md files
    all_dl_errors = []
    for s in skills:
        dl_errs = download_skill_files(gh, repo, s, repo_dir)
        all_dl_errors.extend(dl_errs)

    # Download ACF files into {repo_dir}/ACF/
    if acf_found:
        acf_dir = os.path.join(repo_dir, "ACF")
        os.makedirs(acf_dir, exist_ok=True)
        for acf_path, acf_item, _ in acf_found:
            sha = acf_item.get("sha", "")
            filename = sanitize_path_component(os.path.basename(acf_path))
            local_path = os.path.join(acf_dir, filename)
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                continue
            if sha:
                content, err = download_blob(gh, repo, sha)
                if content is not None:
                    try:
                        with open(local_path, "wb") as out_f:
                            out_f.write(content)
                    except Exception as e:
                        all_dl_errors.append(f"ACF: failed to write {filename}: {e}")
                else:
                    all_dl_errors.append(f"ACF: failed to download {acf_path} (sha {sha}): {err}")

    # Write metadata.json only when at least one skill instance was found.
    metadata = {
        "repo": repo,
        "html_url": f"https://github.com/{repo}",
        "language": language,
        "default_branch": branch,
        "tree_ref": tree_ref,
        "stars": int(stars) if stars.isdigit() else 0,
        "fork": row.get("fork", "").lower() == "true",
        "archived": row.get("archived", "").lower() == "true",
        "skill_count": len(skills),
        "skills": [
            {
                "skill_path": s.skill_path,
                "parent_folder": s.parent_folder,
                "total_files": s.metrics.total_files,
                "references_count": s.metrics.references_count,
                "assets_count": s.metrics.assets_count,
                "scripts_count": s.metrics.scripts_count,
                "other_count": s.metrics.other_count,
            }
            for s in skills
        ],
        "has_README": maintainer_flags["has_README"],
        "has_CONTRIBUTING": maintainer_flags["has_CONTRIBUTING"],
        "has_SECURITY": maintainer_flags["has_SECURITY"],
        "has_CODE_OF_CONDUCT": maintainer_flags["has_CODE_OF_CONDUCT"],
        "has_CLAUDE": acf_flags["has_CLAUDE"],
        "has_AGENTS": acf_flags["has_AGENTS"],
        "has_COPILOT": acf_flags["has_COPILOT"],
        "acf_files": [p for p, _, _ in acf_found],
        "seart": seart_data,
        "generated_at_utc": scanned_at,
        "errors": all_dl_errors,
    }

    os.makedirs(repo_dir, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return skill_rows, all_dl_errors


# ----------------------------
# IO and CLI
# ----------------------------

def load_found_repos(csv_path: str) -> List[Dict[str, str]]:
    if not os.path.exists(csv_path):
        return []
    repos = []
    with open(csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get("repo"):
                repos.append(row)
    return repos


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


def write_dataset_header(out_csv: str) -> None:
    if os.path.exists(out_csv) and os.path.getsize(out_csv) > 0:
        return
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()


def append_dataset_rows(out_csv: str, rows: List[SkillInstanceRow]) -> None:
    """Append all skill rows for one repo in a single open so the CSV never holds a partial repo."""
    if not rows:
        return
    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        for r in rows:
            d = dataclasses.asdict(r)
            seart = d.pop("seart_data", {})
            d.update(seart)
            writer.writerow(d)


def record_name_filtered(log_path: str, repo: str, matched_word: str) -> None:
    """Append a repo that was filtered by name to the name-filter log file."""
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{repo}\t{matched_word}\n")


def record_failure(log_path: str, repo: str, error_type: str, error_message: str) -> None:
    """
    Append one processing failure to the failures TSV log.

    Columns: repo <TAB> error_type <TAB> error_message <TAB> timestamp_utc
    This file is the canonical record for repos that had no rows written to
    the output CSV, enabling later analysis to distinguish:
      - "tree_fetch_failed"  : GitHub returned an error for the tree endpoint
      - "tree_truncated"     : GitHub returned a partial tree
      - "zero_skills_found"  : tree was complete but no matching files existed
      - "exception"          : unexpected runtime error

    Repos that successfully produced dataset rows but had non-fatal download
    warnings are intentionally excluded from this log so it stays focused on
    row-level comparison gaps between stage 2 and stage 3.
    """
    os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
    timestamp = utc_now_iso()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"{repo}\t{error_type}\t{error_message}\t{timestamp}\n")


def write_name_filter_counts(counts_path: str, counts: Dict[str, int], total: int) -> None:
    """Write per-keyword filter counts to a JSON file."""
    os.makedirs(os.path.dirname(counts_path) or ".", exist_ok=True)
    payload = {
        "total_filtered": total,
        "counts_by_keyword": {w: c for w, c in counts.items() if c > 0},
    }
    with open(counts_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def load_already_processed(out_csv: str) -> Set[str]:
    if not os.path.exists(out_csv):
        return set()
    scanned = set()
    try:
        with open(out_csv, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                r = (row.get("repo") or "").strip()
                if r:
                    scanned.add(r)
    except Exception:
        pass
    return scanned


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Re-process found repositories to extract skill datasets.")
    p.add_argument("--found-csv", required=True, help="Input CSV from A script (e.g. outputs/skill_md_scan_results_found.csv)")
    p.add_argument("--out-csv", required=True, help="Output dataset CSV (e.g. outputs/full_skills_instances.csv)")
    p.add_argument("--raw-data-dir", required=True, help="Directory to save downloaded files (e.g. outputs/raw_data)")
    p.add_argument("--match-name", default="SKILL.md", help="Filename to match")
    p.add_argument("--blacklist", default="blacklist.txt", help="Path to blacklist file (owner/repo per line). Default: blacklist.txt")
    p.add_argument("--name-filter-words", default="", help="Comma-separated words to match against repo names (in addition to the built-in list). Repos matching any word are excluded.")
    p.add_argument("--no-name-filter", action="store_true", help="Disable the built-in name filter (REPO_NAME_FILTER_WORDS from filters.py).")
    p.add_argument("--name-filter-log", default="", help="File to record repos excluded by name filter (tab-separated: repo<TAB>matched_word). Defaults to <out-csv dir>/name_filtered_repos.tsv")
    p.add_argument("--failures-log", default="", help="File to record processing failures (tree-fetch errors, zero-skills, exceptions). Defaults to <out-csv dir>/processing_failures.tsv")
    p.add_argument("--resume", action="store_true", help="Skip repos already in out-csv or metadata.json")
    p.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Parallel worker threads for GitHub fetches (default: 1). CSV writes run on the main thread.",
    )
    p.add_argument("--github-token", default="")
    p.add_argument("--github-tokens", default="")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args(argv)


def setup_logging(level: str = "INFO") -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=numeric,
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        stream=sys.stderr,
        force=True,
    )


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    setup_logging(args.log_level)
    
    raw_tokens = args.github_tokens.strip() or args.github_token.strip()
    if raw_tokens:
        tokens = [t.strip() for t in raw_tokens.split(",") if t.strip()]
    else:
        tokens = load_tokens_from_env()

    if not tokens:
        log.warning("No GitHub token detected. Running unauthenticated is highly discouraged for this script.")

    pool = TokenPool(tokens)
    gh = GitHubClient(pool=pool)
    
    repos = load_found_repos(args.found_csv)
    if not repos:
        log.error("No repos found in %s", args.found_csv)
        return 1

    if args.resume:
        try:
            validate_existing_output_header(args.out_csv)
        except ValueError as exc:
            log.error(str(exc))
            return 2

    write_dataset_header(args.out_csv)

    processed_repos = load_already_processed(args.out_csv) if args.resume else set()
    blacklist = load_blacklist(args.blacklist)

    # Build effective name-filter word list (same controls as extract_skill_repos.py).
    name_filter_words: List[str] = [] if args.no_name_filter else list(REPO_NAME_FILTER_WORDS)
    if args.name_filter_words.strip():
        extras = [w.strip() for w in args.name_filter_words.split(",") if w.strip()]
        name_filter_words.extend(extras)

    name_filter_log: str = args.name_filter_log.strip() or os.path.join(
        os.path.dirname(args.out_csv) or ".", "name_filtered_repos.tsv"
    )
    failures_log: str = args.failures_log.strip() or os.path.join(
        os.path.dirname(args.out_csv) or ".", "processing_failures.tsv"
    )

    # Deduplicate by repo — a found CSV can have multiple rows for the same repo
    # (one per SKILL.md match). process_repo handles all instances in a single pass.
    seen: Set[str] = set()
    to_process = []
    skipped_blacklist = 0
    skipped_name_filter = 0
    name_filter_counts: Dict[str, int] = {w: 0 for w in name_filter_words}
    for r in repos:
        repo_name = r["repo"]
        if repo_name in seen:
            continue
        seen.add(repo_name)
        if repo_name in blacklist:
            skipped_blacklist += 1
            continue
        matched_word = repo_name_contains_filter_word(repo_name, name_filter_words)
        if matched_word:
            skipped_name_filter += 1
            name_filter_counts[matched_word] = name_filter_counts.get(matched_word, 0) + 1
            record_name_filtered(name_filter_log, repo_name, matched_word)
            log.debug("Name-filter: skipping %s (matched '%s')", repo_name, matched_word)
            continue
        if args.resume and repo_name in processed_repos:
            # Even if the repo is already in the output CSV, re-queue it when the
            # number of SKILL.md files on disk is lower than what metadata.json
            # recorded.  This catches repos that were processed with the old
            # basename-only download layout and had path collisions.
            language = (r.get("mainLanguage") or "").strip() or "unknown"
            language_safe = language.replace("/", "_").replace("\\", "_")
            repo_safe = repo_name.replace("/", "__")
            repo_dir = os.path.join(args.raw_data_dir, language_safe, repo_safe)
            metadata_path = os.path.join(repo_dir, "metadata.json")
            needs_redownload = False
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, "r", encoding="utf-8") as _f:
                        _meta = json.load(_f)
                    _skill_count = int(_meta.get("skill_count", 0) or 0)
                    if _skill_count > 0:
                        _disk_count = sum(
                            1 for p in pathlib.Path(repo_dir).rglob("SKILL.md")
                            if p.is_file() and p.name == "SKILL.md"
                        )
                        if _disk_count < _skill_count:
                            log.info(
                                "[%s] Disk has %d SKILL.md file(s) but metadata records %d;"
                                " re-queuing for download.",
                                repo_name, _disk_count, _skill_count,
                            )
                            needs_redownload = True
                except Exception:
                    pass
            if not needs_redownload:
                continue
        to_process.append(r)

    if skipped_blacklist:
        log.info("Blacklist: skipping %d blacklisted repositories.", skipped_blacklist)
    if skipped_name_filter:
        log.info(
            "Name-filter: skipping %d repositories (logged to %s).",
            skipped_name_filter,
            name_filter_log,
        )
        breakdown = ", ".join(
            f"'{w}': {name_filter_counts[w]}"
            for w in name_filter_words
            if name_filter_counts.get(w, 0) > 0
        )
        log.info("Name-filter breakdown: %s", breakdown)
        counts_path = os.path.splitext(name_filter_log)[0] + "_counts.json"
        write_name_filter_counts(counts_path, name_filter_counts, skipped_name_filter)
        log.info("Name-filter counts saved to %s", counts_path)

    if not to_process:
        log.info("All repos already processed.")
        return 0

    log.info("Processing %d repositories (concurrency=%d)", len(to_process), args.concurrency)

    processed_count = 0   # skill instance rows written
    zero_skills_count = 0  # repos where tree was fetched but no matching files found
    error_count = 0

    try:
        from tqdm import tqdm
        from tqdm.contrib.logging import logging_redirect_tqdm
        has_tqdm = True
    except ImportError:
        has_tqdm = False

    def worker(row):
        log.info("Processing repo: %s", row["repo"])
        return process_repo(gh, row, args.raw_data_dir, args.match_name)

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futures = {ex.submit(worker, row): row["repo"] for row in to_process}

        def _handle_result(repo: str, skill_rows: list, errs: list) -> None:
            nonlocal processed_count, zero_skills_count, error_count
            append_dataset_rows(args.out_csv, skill_rows)
            processed_count += len(skill_rows)
            if errs:
                if errs == ["zero_skills_found"]:
                    zero_skills_count += 1
                    log.debug("[%s] zero_skills_found: tree fetched but no matching files", repo)
                    record_failure(failures_log, repo, "zero_skills_found", "")
                else:
                    error_count += 1
                    for e in errs:
                        log.warning("[%s] %s", repo, e)
                    # Only repos that produced no dataset rows belong in the
                    # failures log. Successful rows with download warnings are
                    # still valuable outputs and should not be mixed into the
                    # "why is this repo missing?" artifact.
                    if not skill_rows:
                        if len(errs) == 1 and errs[0].startswith("Tree fetch failed: "):
                            detail = errs[0].split(": ", 1)[1]
                            failure_type = "tree_truncated" if detail == "tree_truncated" else "tree_fetch_failed"
                            record_failure(failures_log, repo, failure_type, detail)
                        else:
                            record_failure(failures_log, repo, "tree_fetch_failed", "; ".join(errs))

        if has_tqdm:
            with logging_redirect_tqdm(), tqdm(total=len(to_process), desc="Processing", unit="repo", file=sys.stderr) as pbar:
                for fut in as_completed(futures):
                    repo = futures[fut]
                    try:
                        skill_rows, errs = fut.result()
                        _handle_result(repo, skill_rows, errs)
                    except Exception as e:
                        error_count += 1
                        log.exception("[%s] Unexpected error: %s", repo, e)
                        record_failure(failures_log, repo, "exception", str(e))

                    pbar.update(1)
        else:
            for fut in as_completed(futures):
                repo = futures[fut]
                try:
                    skill_rows, errs = fut.result()
                    _handle_result(repo, skill_rows, errs)
                except Exception as e:
                    error_count += 1
                    log.exception("[%s] Unexpected error: %s", repo, e)
                    record_failure(failures_log, repo, "exception", str(e))

    log.info(
        "Done. Skill rows written: %d | Zero-skills (false-negative candidates): %d | Repos with errors: %d",
        processed_count, zero_skills_count, error_count,
    )
    log.info("Failures log: %s", failures_log)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
