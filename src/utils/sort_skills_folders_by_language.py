#!/usr/bin/env python3
"""
sort_skills_folders_by_language.py

Reorganises a flat raw_data directory produced by an older run of
C_generate_dataset.py (where repos were stored as raw_data/{owner__repo}/)
into the language-partitioned layout used by the current version:

    raw_data/{language}/{owner__repo}/

The language is read from the repo's metadata.json:
  - metadata["language"]  (written by the current C_generate_dataset.py)
  - metadata["seart"]["mainLanguage"]  (fallback for older metadata.json files)

If neither field is present or non-empty, the repo is moved into an
"unknown" subfolder.

Usage
-----
    python sort_skills_folders_by_language.py --raw-data-dir outputs/raw_data
    python sort_skills_folders_by_language.py --raw-data-dir outputs/raw_data --dry-run

Options
-------
--raw-data-dir  Path to the flat raw_data directory.
--dry-run       Print what would be moved without actually moving anything.
--log-level     Logging verbosity (DEBUG, INFO, WARNING, ERROR). Default: INFO.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import sys
from typing import Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_language_from_metadata(metadata_path: str) -> Optional[str]:
    """Return the language string from metadata.json, or None on failure."""
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as exc:
        log.warning("Could not parse %s: %s", metadata_path, exc)
        return None

    # Preferred: top-level "language" key (written by current C_generate_dataset.py)
    lang = (meta.get("language") or "").strip()
    if lang:
        return lang

    # Fallback: SEART block written by older versions
    seart = meta.get("seart") or {}
    lang = (seart.get("mainLanguage") or "").strip()
    return lang or None


def _language_to_safe_dir(language: Optional[str]) -> str:
    """Convert a language string to a safe directory name."""
    if not language:
        return "unknown"
    return language.replace("/", "_").replace("\\", "_")


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def sort_folders(raw_data_dir: str, dry_run: bool) -> None:
    """
    Scan raw_data_dir for flat {owner__repo} directories and move each one
    into raw_data_dir/{language}/{owner__repo}/.

    Directories that already sit inside a sub-directory (i.e. depth > 1)
    are assumed to already be in the language-partitioned layout and are
    skipped.
    """
    if not os.path.isdir(raw_data_dir):
        log.error("Directory does not exist: %s", raw_data_dir)
        sys.exit(1)

    entries = sorted(os.listdir(raw_data_dir))
    flat_dirs = []
    for entry in entries:
        full = os.path.join(raw_data_dir, entry)
        if not os.path.isdir(full):
            continue
        # A flat repo dir contains a metadata.json directly inside it.
        # A language-partition dir would contain sub-dirs, each with their own metadata.json.
        metadata_path = os.path.join(full, "metadata.json")
        if os.path.isfile(metadata_path):
            flat_dirs.append((entry, full, metadata_path))
        else:
            # Distinguish a true language-partition dir (whose children have metadata.json)
            # from a repo dir that is simply missing its metadata.json.
            child_entries = os.listdir(full)
            child_has_metadata = any(
                os.path.isfile(os.path.join(full, child, "metadata.json"))
                for child in child_entries
                if os.path.isdir(os.path.join(full, child))
            )
            if child_has_metadata:
                log.debug(
                    "Skipping '%s' — looks like a language-partition directory (children have metadata.json).",
                    entry,
                )
            else:
                log.warning(
                    "Skipping '%s' — no metadata.json found and does not look like a language-partition "
                    "directory. This repo may be missing its metadata.json and will not be moved. "
                    "Move it manually to the correct language subfolder.",
                    entry,
                )

    if not flat_dirs:
        log.info("No flat repo directories found in %s — nothing to do.", raw_data_dir)
        return

    log.info("Found %d flat repo director%s to sort.", len(flat_dirs), "y" if len(flat_dirs) == 1 else "ies")

    moved = 0
    skipped = 0
    errors = 0

    for repo_safe, src_path, metadata_path in flat_dirs:
        language = _read_language_from_metadata(metadata_path)
        lang_dir = _language_to_safe_dir(language)

        dest_parent = os.path.join(raw_data_dir, lang_dir)
        dest_path = os.path.join(dest_parent, repo_safe)

        if os.path.exists(dest_path):
            log.warning("Destination already exists, skipping '%s' → '%s'.", src_path, dest_path)
            skipped += 1
            continue

        log.info("%s'%s' → '%s'", "[DRY RUN] Would move " if dry_run else "Moving ", src_path, dest_path)

        if dry_run:
            moved += 1
            continue

        try:
            os.makedirs(dest_parent, exist_ok=True)
            shutil.move(src_path, dest_path)
            moved += 1
        except Exception as exc:
            log.error("Failed to move '%s': %s", src_path, exc)
            errors += 1

    label = "Would move" if dry_run else "Moved"
    log.info("Done. %s: %d, Skipped: %d, Errors: %d", label, moved, skipped, errors)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Reorganise a flat raw_data directory into language-partitioned subfolders.",
    )
    p.add_argument(
        "--raw-data-dir",
        required=True,
        help="Path to the flat raw_data directory (e.g. outputs/raw_data).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be moved without making any changes.",
    )
    p.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return p.parse_args(argv)


def setup_logging(level: str) -> None:
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=numeric,
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        stream=sys.stderr,
        force=True,
    )


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    setup_logging(args.log_level)

    if args.dry_run:
        log.info("DRY RUN — no files will be moved.")

    sort_folders(args.raw_data_dir, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
