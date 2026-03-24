#!/usr/bin/env python3
"""
cleanup_collision_folders.py

Remove stale basename-only skill folders left behind by the old download layout.

When generate_dataset.py used os.path.basename(parent_folder) as the local
folder name, skills at e.g. Packs/Agents/src and Packs/ContentAnalysis/src
were both written to <repo_dir>/src/.  The fix writes the full sanitized path
(Packs/Agents/src, Packs/ContentAnalysis/src), but the old single-component
folders (Agents/, ContentAnalysis/, src/, …) may still exist alongside them.

This script:
1. Reads metadata.json for each repo to get the expected skill parent_folder paths.
2. Builds the set of valid top-level directory names under repo_dir (i.e. the
   first component of each sanitized parent_folder, plus "ACF" which is always
   kept).
3. Deletes any immediate subdirectory of repo_dir that is NOT in that valid set.

Usage:
    uv run python src/utils/cleanup_collision_folders.py --raw-data-dir outputs/raw_data
    uv run python src/utils/cleanup_collision_folders.py --raw-data-dir outputs/raw_data --dry-run
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

_WINDOWS_INVALID_RE = re.compile(r'[\\/:*?"<>|]')
_ALWAYS_KEEP = {"ACF"}


def sanitize_component(name: str) -> str:
    return _WINDOWS_INVALID_RE.sub("_", name)


def sanitize_relative_path(rel_path: str) -> str:
    parts = rel_path.replace("\\", "/").split("/")
    return "/".join(sanitize_component(p) for p in parts if p)


def valid_top_level_dirs(skills: list[dict]) -> set[str]:
    """
    Return the set of first path components for all expected skill folders.
    A skill at parent_folder="" (repo root) maps to the special name "root".
    """
    valid: set[str] = set(_ALWAYS_KEEP)
    for s in skills:
        parent = (s.get("parent_folder") or "").strip()
        if not parent:
            valid.add("root")
        else:
            sanitized = sanitize_relative_path(parent)
            top = sanitized.split("/")[0]
            valid.add(top)
    return valid


def cleanup_repo(repo_dir: Path, dry_run: bool) -> tuple[int, int]:
    """
    Remove stale subdirectories from repo_dir.
    Returns (removed_count, kept_count).
    """
    metadata_path = repo_dir / "metadata.json"
    if not metadata_path.exists():
        return 0, 0

    try:
        with metadata_path.open(encoding="utf-8") as fh:
            meta = json.load(fh)
    except Exception as exc:
        log.warning("Could not read %s: %s", metadata_path, exc)
        return 0, 0

    skills = meta.get("skills", [])
    if not skills:
        return 0, 0

    valid = valid_top_level_dirs(skills)
    removed = kept = 0

    for child in sorted(repo_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name in valid:
            kept += 1
            continue
        # Not in the expected set — stale old-layout folder
        log.info("  removing stale folder: %s", child)
        if not dry_run:
            shutil.rmtree(child)
        removed += 1

    return removed, kept


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Remove stale basename-only skill folders from raw_data repos."
    )
    parser.add_argument(
        "--raw-data-dir",
        required=True,
        metavar="DIR",
        help="Root raw_data directory (language subfolders expected as immediate children).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without actually deleting anything.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    root = Path(args.raw_data_dir).resolve()
    if not root.is_dir():
        log.error("Directory does not exist: %s", root)
        return

    if args.dry_run:
        log.info("DRY RUN — no files will be deleted.")

    total_removed = total_kept = repos_cleaned = 0

    for lang_dir in sorted(root.iterdir()):
        if not lang_dir.is_dir():
            continue
        for repo_dir in sorted(lang_dir.iterdir()):
            if not repo_dir.is_dir():
                continue
            removed, kept = cleanup_repo(repo_dir, dry_run=args.dry_run)
            if removed:
                repos_cleaned += 1
                log.debug("[%s/%s] removed=%d kept=%d", lang_dir.name, repo_dir.name, removed, kept)
            total_removed += removed
            total_kept += kept

    action = "Would remove" if args.dry_run else "Removed"
    log.info(
        "Done. %s %d stale folder(s) across %d repo(s). %d valid folder(s) kept.",
        action, total_removed, repos_cleaned, total_kept,
    )


if __name__ == "__main__":
    main()
