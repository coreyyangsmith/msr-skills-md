#!/usr/bin/env python3
"""
generate_language_sample.py

RQ3: Random sample of SKILL.md files from a raw_data root folder.

Recursively walks a root folder and collects every file named exactly
``SKILL.md`` at any depth beneath it.  Only the exact filename is matched
(case-sensitive).

A random sample of *n* files is drawn from the full corpus and copied into
an output directory that mirrors the original relative path structure:

    <out_dir>/<language>/<repo>/<...>/SKILL.md

Usage:
    uv run python src/rq3/generate_language_sample.py \\
        --root outputs/raw_data \\
        --n 50 \\
        --out-dir outputs/rq3/language_sample

    uv run python src/rq3/generate_language_sample.py \\
        --root outputs/raw_data \\
        --n 100 \\
        --seed 42 \\
        --out-dir outputs/rq3/language_sample

    uv run python src/rq3/generate_language_sample.py \\
        --root outputs/raw_data/Python \\
        --n 370 --seed 42 \\
        --allowed-repos-csv data/data_after_relevance_filter/data_after_filter.csv \\
        --allowed-main-language Python \\
        --clean-out-dir \\
        --out-dir outputs/rq3/language_sample/Python
    uv run python src/rq3/generate_language_sample.py --root outputs/raw_data/TypeScript --n 365 --seed 42 --out-dir outputs/rq3/language_sample/TypeScript
"""

from __future__ import annotations

import argparse
import csv
import logging
import random
import shutil
import sys
from pathlib import Path

log = logging.getLogger(__name__)

SKILL_FILENAME = "SKILL.md"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def repo_from_skill_path(root: Path, skill_path: Path) -> str | None:
    """
    Decode owner/repo from a SKILL.md path under *root*.

    Expected layout: ``<root>/<owner__repo>/.../SKILL.md`` (one ``__`` splits
    owner and repo name in the first path segment).
    """
    try:
        rel = skill_path.relative_to(root)
    except ValueError:
        return None
    if not rel.parts:
        return None
    top = rel.parts[0]
    if "__" not in top:
        return None
    owner, repo_name = top.split("__", 1)
    if not owner or not repo_name:
        return None
    return f"{owner}/{repo_name}"


def load_allowed_repos_from_csv(path: Path, main_language: str | None) -> set[str]:
    """
    Load allowed owner/repo identifiers from a SEART-style CSV (``name`` or
    ``repo`` column). When *main_language* is set, keep only rows whose
    ``mainLanguage`` matches (case-insensitive).
    """
    allowed: set[str] = set()
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if main_language is not None:
                lang = (row.get("mainLanguage") or "").strip()
                if lang.lower() != main_language.strip().lower():
                    continue
            name = (row.get("name") or row.get("repo") or "").strip()
            if name:
                allowed.add(name)
    log.info(
        "Loaded %d allowed repo(s) from %s%s",
        len(allowed),
        path,
        f" (mainLanguage={main_language!r})" if main_language else "",
    )
    return allowed


def collect_skill_files(root: Path) -> list[Path]:
    """
    Return a list of all SKILL.md paths found anywhere under *root* via a
    full recursive scan.  Only files whose name is exactly ``SKILL.md`` are
    matched (rglob pattern already ensures this, but the name check guards
    against any case-folding behaviour on case-insensitive filesystems).
    """
    log.info("Recursively scanning all SKILL.md files under %s", root)

    matches = [
        p
        for p in root.rglob(SKILL_FILENAME)
        if p.is_file() and p.name == SKILL_FILENAME
    ]

    log.info("Total SKILL.md files found: %d", len(matches))
    return matches


def filter_skill_files_by_allowed_repos(
    matches: list[Path],
    root: Path,
    allowed_repos: set[str],
) -> list[Path]:
    """Keep only SKILL.md files whose decoded repo is in *allowed_repos*."""
    kept: list[Path] = []
    for p in matches:
        repo = repo_from_skill_path(root, p)
        if repo and repo in allowed_repos:
            kept.append(p)
    log.info(
        "After allowed-repos filter: %d / %d SKILL.md file(s)",
        len(kept),
        len(matches),
    )
    return kept


def sample_and_copy(
    all_files: list[Path],
    root: Path,
    n: int,
    out_dir: Path,
    seed: int | None,
) -> list[Path]:
    """
    Randomly sample *n* files from *all_files*, copy each to *out_dir*
    preserving the path relative to *root*, and return the list of sampled
    source paths.
    """
    if n > len(all_files):
        log.warning(
            "Requested sample size %d exceeds corpus size %d; using all files.",
            n,
            len(all_files),
        )
        n = len(all_files)

    rng = random.Random(seed)
    sampled: list[Path] = rng.sample(all_files, n)

    out_dir.mkdir(parents=True, exist_ok=True)

    for src in sampled:
        rel = src.relative_to(root)
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log.debug("  copied %s → %s", rel, dst)

    return sampled


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly sample SKILL.md files from a raw_data root folder "
            "and copy them to an output directory."
        ),
    )
    parser.add_argument(
        "--root",
        required=True,
        metavar="DIR",
        help="Root folder to recursively scan for SKILL.md files.",
    )
    parser.add_argument(
        "--n",
        required=True,
        type=int,
        metavar="N",
        help="Number of SKILL.md files to sample.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        metavar="DIR",
        help="Output directory; sampled files are written here preserving relative paths.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        metavar="INT",
        help="Random seed for reproducibility (optional).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    parser.add_argument(
        "--allowed-repos-csv",
        default="",
        metavar="CSV",
        help=(
            "Optional SEART-style CSV (e.g. data_after_relevance_filter). "
            "Only SKILL.md files under repos listed here are eligible."
        ),
    )
    parser.add_argument(
        "--allowed-main-language",
        default="",
        metavar="LANG",
        help=(
            "When using --allowed-repos-csv, restrict CSV rows to this mainLanguage "
            "(e.g. Python). Recommended when --root is a single-language raw_data folder."
        ),
    )
    parser.add_argument(
        "--clean-out-dir",
        action="store_true",
        help="Remove output directory before writing (avoids stale copies from prior runs).",
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

    if args.n <= 0:
        log.error("--n must be a positive integer, got %d", args.n)
        sys.exit(1)

    out_dir = Path(args.out_dir).resolve()

    all_files = collect_skill_files(root)
    if not all_files:
        log.error("No SKILL.md files found under %s", root)
        sys.exit(1)

    if args.allowed_repos_csv:
        csv_path = Path(args.allowed_repos_csv).resolve()
        if not csv_path.is_file():
            log.error("Allowed-repos CSV not found: %s", csv_path)
            sys.exit(1)
        lang = args.allowed_main_language.strip() or None
        allowed = load_allowed_repos_from_csv(csv_path, lang)
        if not allowed:
            log.error("No repos loaded from %s with the given filters.", csv_path)
            sys.exit(1)
        all_files = filter_skill_files_by_allowed_repos(all_files, root, allowed)
        if not all_files:
            log.error("No SKILL.md files left after allowed-repos filter.")
            sys.exit(1)

    if args.clean_out_dir and out_dir.exists():
        log.info("Removing existing output directory: %s", out_dir)
        shutil.rmtree(out_dir)

    sampled = sample_and_copy(
        all_files=all_files,
        root=root,
        n=args.n,
        out_dir=out_dir,
        seed=args.seed,
    )

    log.info(
        "Done. Sampled %d / %d SKILL.md file(s) → %s",
        len(sampled),
        len(all_files),
        out_dir,
    )


if __name__ == "__main__":
    main()
