#!/usr/bin/env python3
"""
B_generate_dataset.py

Re-processes repositories from A_extract_skill_repos.py output to:
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
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set, Tuple

from github_client import GitHubClient, TokenPool, load_tokens_from_env

log = logging.getLogger(__name__)

# All columns present in a SEART CSV export (mirrors A_extract_skill_repos.py).
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
class RepoDatasetRow:
    repo: str
    default_branch: str
    stars: str
    fork: str
    archived: str
    html_url: str
    skill_count: int = 0
    skill_paths: str = ""
    total_files_in_skills: int = 0
    references_file_count: int = 0
    assets_file_count: int = 0
    scripts_file_count: int = 0
    other_file_count: int = 0
    scanned_at_utc: str = ""
    has_CLAUDE: int = 0
    has_AGENTS: int = 0
    has_COPILOT: int = 0
    # Original SEART columns carried through from the input CSV.
    seart_data: Dict[str, str] = dataclasses.field(default_factory=dict)


# Ordered list of dataset-specific output columns (everything except seart_data).
_DATASET_COLUMNS: List[str] = [
    f.name for f in dataclasses.fields(RepoDatasetRow) if f.name != "seart_data"
]

# Full output schema: dataset columns first, then all SEART columns.
OUTPUT_COLUMNS: List[str] = _DATASET_COLUMNS + SEART_COLUMNS


# ----------------------------
# Logic
# ----------------------------

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_repo_tree(gh: GitHubClient, repo: str, branch: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Fetch the full recursive tree for a repo branch.
    Returns (tree_items, error_message).
    """
    owner, name = repo.split("/", 1)
    # The API is /repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1
    status, data, err = gh.request_json("GET", f"/repos/{owner}/{name}/git/trees/{branch}", params={"recursive": "1"})
    
    if status == 404 or status == 409: # 409 happens for empty repositories
        return [], "tree_not_found"
    if status == 403 or status == 429:
        # Should not reach here typically due to retry, but if max_retries hit
        return [], "rate_limited"
    if status != 200 or not isinstance(data, dict):
        return [], err or f"http_{status}"

    if data.get("truncated"):
        log.warning("Tree for %s is truncated. Some files may be missed.", repo)

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
        
        # Collect all blobs under this parent
        # If parent is "", it matches everything, but usually a skill in root means
        # the whole repo is the skill. To be safe and avoid downloading the entire repo
        # if SKILL.md is at root, we still download everything, but we should be mindful.
        # Wait, the prompt says "Wherever the path is of the target SKILL.md file, the immediate parent folder (entire folder, and all its contents) should be downloaded."
        
        prefix = parent + "/" if parent else ""
        
        files_in_skill = []
        for item in tree_items:
            if item.get("type") == "blob":
                item_path = item.get("path", "")
                if parent == "":
                    # if parent is root, all files are in it
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


def download_skill_files(gh: GitHubClient, repo: str, skill: SkillInstance, raw_data_dir: str) -> List[str]:
    """
    Download all files for a skill instance into raw_data_dir.
    Returns list of errors if any.
    """
    repo_safe = repo.replace("/", "__")
    
    errors = []
    
    prefix = skill.parent_folder + "/" if skill.parent_folder else ""
    
    for f in skill.files:
        path = f.get("path", "")
        sha = f.get("sha", "")
        
        if path.startswith(prefix):
            rel_path = path[len(prefix):]
        else:
            rel_path = path
            
        # Determine local path
        # raw_data/owner__repo/skill_folder_name/rel_path
        folder_name = os.path.basename(skill.parent_folder) if skill.parent_folder else "root"
        local_path = os.path.join(raw_data_dir, repo_safe, folder_name, rel_path)
        
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
    match_name: str
) -> Tuple[Optional[RepoDatasetRow], List[str]]:
    """
    Process a single repository.
    Returns (RepoDatasetRow, list_of_errors).
    """
    repo = row["repo"]
    branch = row.get("default_branch") or "main"
    
    repo_safe = repo.replace("/", "__")
    metadata_path = os.path.join(raw_data_dir, repo_safe, "metadata.json")
    
    # Check if already processed via metadata
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                json.load(f)  # ensure valid json
                
            # Reconstruct row from metadata
            # This allows resume to also yield the row for the CSV if needed
            # (Though our main loop writes CSV incrementally, we might just return None 
            # if we assume it's already in the CSV).
            # To be safe and simple, we'll return None so we just skip it.
            return None, []
        except Exception:
            pass # corrupted metadata, re-process
            
    tree_items, tree_err = fetch_repo_tree(gh, repo, branch)
    if tree_err:
        return None, [f"Tree fetch failed: {tree_err}"]
        
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

    # Carry through every original SEART column from the input row.
    seart_data = {col: (row.get(col) or "") for col in SEART_COLUMNS}

    # Create the dataset row
    dataset_row = RepoDatasetRow(
        repo=repo,
        default_branch=branch,
        stars=row.get("stars", ""),
        fork=row.get("fork", ""),
        archived=row.get("archived", ""),
        html_url=f"https://github.com/{repo}",
        skill_count=len(skills),
        skill_paths=";".join(s.skill_path for s in skills),
        scanned_at_utc=utc_now_iso(),
        seart_data=seart_data,
    )

    # Set ACF presence flags (1/0) on the dataset row.
    for _acf_path, _acf_item, _acf_attr in acf_found:
        setattr(dataset_row, _acf_attr, 1)
    
    for s in skills:
        dataset_row.total_files_in_skills += s.metrics.total_files
        dataset_row.references_file_count += s.metrics.references_count
        dataset_row.assets_file_count += s.metrics.assets_count
        dataset_row.scripts_file_count += s.metrics.scripts_count
        dataset_row.other_file_count += s.metrics.other_count
        
    # Download SKILL.md files
    all_dl_errors = []
    for s in skills:
        dl_errs = download_skill_files(gh, repo, s, raw_data_dir)
        all_dl_errors.extend(dl_errs)

    # Download ACF files into raw_data/{repo_safe}/ACF/
    if acf_found:
        acf_dir = os.path.join(raw_data_dir, repo_safe, "ACF")
        os.makedirs(acf_dir, exist_ok=True)
        for acf_path, acf_item, _ in acf_found:
            sha = acf_item.get("sha", "")
            filename = os.path.basename(acf_path)
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
        
    # Write metadata.json
    metadata = {
        "repo": repo,
        "html_url": dataset_row.html_url,
        "default_branch": branch,
        "stars": int(dataset_row.stars) if dataset_row.stars.isdigit() else 0,
        "fork": dataset_row.fork.lower() == "true",
        "archived": dataset_row.archived.lower() == "true",
        "skill_count": dataset_row.skill_count,
        "skills": [
            {
                "skill_path": s.skill_path,
                "parent_folder": s.parent_folder,
                "total_files": s.metrics.total_files,
                "references_count": s.metrics.references_count,
                "assets_count": s.metrics.assets_count,
                "scripts_count": s.metrics.scripts_count,
                "other_count": s.metrics.other_count
            }
            for s in skills
        ],
        "has_CLAUDE": dataset_row.has_CLAUDE,
        "has_AGENTS": dataset_row.has_AGENTS,
        "has_COPILOT": dataset_row.has_COPILOT,
        "acf_files": [p for p, _, _ in acf_found],
        "seart": seart_data,
        "generated_at_utc": dataset_row.scanned_at_utc,
        "errors": all_dl_errors
    }
    
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
        
    return dataset_row, all_dl_errors


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


def write_dataset_header(out_csv: str) -> None:
    if os.path.exists(out_csv) and os.path.getsize(out_csv) > 0:
        return
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()


def append_dataset_row(out_csv: str, r: RepoDatasetRow) -> None:
    with open(out_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        d = dataclasses.asdict(r)
        seart = d.pop("seart_data", {})
        d.update(seart)
        writer.writerow(d)


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
    p.add_argument("--resume", action="store_true", help="Skip repos already in out-csv or metadata.json")
    p.add_argument("--concurrency", type=int, default=4, help="Worker threads")
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
        
    write_dataset_header(args.out_csv)
    
    processed_repos = load_already_processed(args.out_csv) if args.resume else set()
    
    to_process = []
    for r in repos:
        if args.resume and r["repo"] in processed_repos:
            continue
        to_process.append(r)
        
    if not to_process:
        log.info("All repos already processed.")
        return 0
        
    log.info("Processing %d repositories (concurrency=%d)", len(to_process), args.concurrency)
    
    processed_count = 0
    error_count = 0
    
    try:
        from tqdm import tqdm
        from tqdm.contrib.logging import logging_redirect_tqdm
        has_tqdm = True
    except ImportError:
        has_tqdm = False
        
    def worker(row):
        return process_repo(gh, row, args.raw_data_dir, args.match_name)
        
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as ex:
        futures = {ex.submit(worker, row): row["repo"] for row in to_process}
        
        if has_tqdm:
            with logging_redirect_tqdm(), tqdm(total=len(to_process), desc="Processing", unit="repo", file=sys.stderr) as pbar:
                for fut in as_completed(futures):
                    repo = futures[fut]
                    try:
                        row, errs = fut.result()
                        if row is not None:
                            append_dataset_row(args.out_csv, row)
                            processed_count += 1
                        if errs:
                            error_count += 1
                            for e in errs:
                                log.warning("[%s] %s", repo, e)
                    except Exception as e:
                        error_count += 1
                        log.exception("[%s] Unexpected error: %s", repo, e)
                        
                    pbar.update(1)
        else:
            for fut in as_completed(futures):
                repo = futures[fut]
                try:
                    row, errs = fut.result()
                    if row is not None:
                        append_dataset_row(args.out_csv, row)
                        processed_count += 1
                    if errs:
                        error_count += 1
                        for e in errs:
                            log.warning("[%s] %s", repo, e)
                except Exception as e:
                    error_count += 1
                    log.exception("[%s] Unexpected error: %s", repo, e)

    log.info("Done. Processed: %d, Errors: %d", processed_count, error_count)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
