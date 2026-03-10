#!/usr/bin/env python3
"""
retrieve_language_metadata.py

RQ3: Language-level summary of SKILL.md prevalence.

Walks a root folder whose immediate children are language subfolders (e.g.
outputs/raw_data/Python, outputs/raw_data/Go, …).  Each language subfolder
contains one subfolder per repository, and each repo subfolder may contain a
metadata.json produced by C_generate_dataset.py.

For every language folder the script emits one JSON summary file:
    <root>/<language>_summary.json

Usage:
    uv run python src/rq3/retrieve_language_metadata.py \
        --root outputs/raw_data

    uv run python src/rq3/retrieve_language_metadata.py \
        --root outputs/raw_data --out-dir outputs/rq3

    uv run python src/rq3/retrieve_language_metadata.py --root outputs/raw_data --out-dir outputs/rq3        
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def count_skill_md_files(repo_dir: Path) -> int:
    """Return total SKILL.md files found anywhere under *repo_dir*."""
    return sum(1 for _ in repo_dir.rglob("SKILL.md"))


def summarise_language(lang_dir: Path) -> dict[str, Any]:
    """
    Walk *lang_dir* (one immediate level of repo subfolders) and return a
    summary dict.

    For each repo subfolder the script tries to read ``metadata.json`` first
    (for rich metadata), then falls back to a raw filesystem count of
    ``SKILL.md`` files.
    """
    language = lang_dir.name
    repos: list[dict[str, Any]] = []

    for repo_dir in sorted(lang_dir.iterdir()):
        if not repo_dir.is_dir():
            continue

        meta_path = repo_dir / "metadata.json"
        if meta_path.exists():
            try:
                with meta_path.open(encoding="utf-8") as fh:
                    meta: dict[str, Any] = json.load(fh)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Could not read %s: %s", meta_path, exc)
                meta = {}
        else:
            meta = {}

        # Prefer skill_count from metadata; fall back to filesystem walk.
        if "skill_count" in meta:
            skill_count = int(meta["skill_count"])
        else:
            skill_count = count_skill_md_files(repo_dir)

        repo_entry: dict[str, Any] = {
            "repo_folder": repo_dir.name,
            "repo": meta.get("repo", repo_dir.name.replace("__", "/")),
            "skill_count": skill_count,
            "stars": meta.get("stars"),
            "fork": meta.get("fork"),
            "archived": meta.get("archived"),
            "has_CLAUDE": meta.get("has_CLAUDE"),
            "has_AGENTS": meta.get("has_AGENTS"),
            "has_COPILOT": meta.get("has_COPILOT"),
        }
        repos.append(repo_entry)

    total_repos = len(repos)
    total_skill_files = sum(r["skill_count"] for r in repos)
    repos_with_skills = sum(1 for r in repos if r["skill_count"] > 0)

    summary: dict[str, Any] = {
        "language": language,
        "total_repos": total_repos,
        "repos_with_skill_md": repos_with_skills,
        "repos_without_skill_md": total_repos - repos_with_skills,
        "total_skill_md_files": total_skill_files,
        "mean_skill_md_per_repo": round(total_skill_files / total_repos, 4) if total_repos else 0,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "repos": repos,
    }
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate per-language SKILL.md summary JSON files from a raw_data root folder.",
    )
    parser.add_argument(
        "--root",
        required=True,
        metavar="DIR",
        help="Root folder whose immediate children are language subfolders.",
    )
    parser.add_argument(
        "--out-dir",
        metavar="DIR",
        default=None,
        help=(
            "Directory where summary JSON files are written. "
            "Defaults to --root (one file per language alongside the language folders)."
        ),
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    root = Path(args.root).resolve()
    if not root.is_dir():
        log.error("Root directory does not exist: %s", root)
        sys.exit(1)

    out_dir = Path(args.out_dir).resolve() if args.out_dir else root
    out_dir.mkdir(parents=True, exist_ok=True)

    lang_dirs = sorted(d for d in root.iterdir() if d.is_dir())
    if not lang_dirs:
        log.warning("No subdirectories found in %s", root)
        return

    log.info("Found %d language folder(s) under %s", len(lang_dirs), root)

    for lang_dir in lang_dirs:
        log.info("Processing language: %s", lang_dir.name)
        summary = summarise_language(lang_dir)

        out_path = out_dir / f"{lang_dir.name}_summary.json"
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2, ensure_ascii=False)

        log.info(
            "  repos=%d  with_skill=%d  total_skill_files=%d  → %s",
            summary["total_repos"],
            summary["repos_with_skill_md"],
            summary["total_skill_md_files"],
            out_path,
        )

    log.info("Done. %d summary file(s) written to %s", len(lang_dirs), out_dir)


if __name__ == "__main__":
    main()
