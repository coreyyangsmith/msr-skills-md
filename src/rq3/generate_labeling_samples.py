#!/usr/bin/env python3
"""
generate_labeling_samples.py

RQ3: Split a folder of SKILL.md files into labeling buckets.

Recursively walks a root folder and collects every file named exactly
``SKILL.md`` at any depth beneath it.  A random sample is drawn from the
full corpus and distributed into three labeling subfolders:

    <out_dir>/both/     – items seen by both labelers (overlap/agreement set)
    <out_dir>/A/        – items assigned only to labeler A
    <out_dir>/B/        – items assigned only to labeler B

Each subfolder mirrors the original relative path structure from *root*.

The three bucket sizes are supplied via --both, --corey, and --marcel.
Sampling is done without replacement across all three buckets (i.e. the
same SKILL.md will not appear in more than one bucket).

Usage:
    uv run python src/rq3/generate_labeling_samples.py \\
        --root outputs/rq3/language_sample \\
        --both 55 \\
        --A 154 \\
        --B 155 \\
        --out-dir outputs/rq3/labeling_samples \\
        --seed 42

    uv run python src/rq3/generate_labeling_samples.py --root outputs/rq3/language_sample/Python --both 55 --A 154 --B 154 --out-dir outputs/rq3/labeling_samples/Python --seed 42
    uv run python src/rq3/generate_labeling_samples.py --root outputs/rq3/language_sample/TypeScript --both 55 --A 155 --B 155 --out-dir outputs/rq3/labeling_samples/TypeScript --seed 42

"""

from __future__ import annotations

import argparse
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


def collect_skill_files(root: Path) -> list[Path]:
    """Return all SKILL.md paths found anywhere under *root*."""
    log.info("Recursively scanning all SKILL.md files under %s", root)
    matches = [
        p
        for p in root.rglob(SKILL_FILENAME)
        if p.is_file() and p.name == SKILL_FILENAME
    ]
    log.info("Total SKILL.md files found: %d", len(matches))
    return matches


def copy_files(files: list[Path], root: Path, dest: Path) -> None:
    """Copy *files* into *dest*, preserving paths relative to *root*."""
    dest.mkdir(parents=True, exist_ok=True)
    for src in files:
        rel = src.relative_to(root)
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log.debug("  copied %s → %s", rel, dst)


def split_into_buckets(
    all_files: list[Path],
    root: Path,
    out_dir: Path,
    n_both: int,
    n_A: int,
    n_B: int,
    seed: int | None,
) -> dict[str, list[Path]]:
    """
    Randomly sample (n_both + n_A + n_B) files from *all_files*
    without replacement, partition them into the three buckets, copy each
    bucket to its subfolder under *out_dir*, and return the partition map.
    """
    total = n_both + n_A + n_B
    corpus_size = len(all_files)

    if total > corpus_size:
        log.error(
            "Requested total (%d) exceeds corpus size (%d). "
            "Reduce --both / --A / --B.",
            total,
            corpus_size,
        )
        sys.exit(1)

    rng = random.Random(seed)
    pool: list[Path] = rng.sample(all_files, total)

    # Partition sequentially after a single shuffle so every item ends up in
    # exactly one bucket.
    buckets: dict[str, list[Path]] = {
        "both": pool[:n_both],
        "A": pool[n_both : n_both + n_A],
        "B": pool[n_both + n_A :],
    }

    for name, files in buckets.items():
        dest = out_dir / name
        log.info("Writing %d files → %s", len(files), dest)
        copy_files(files, root, dest)

    return buckets


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly split SKILL.md files from a root folder into three "
            "labeling buckets: 'both', 'corey', and 'marcel'."
        ),
    )
    parser.add_argument(
        "--root",
        required=True,
        metavar="DIR",
        help="Root folder to recursively scan for SKILL.md files.",
    )
    parser.add_argument(
        "--both",
        required=True,
        type=int,
        metavar="N",
        help="Number of SKILL.md files assigned to the shared 'both' bucket.",
    )
    parser.add_argument(
        "--A",
        required=True,
        type=int,
        metavar="N",
        help="Number of SKILL.md files assigned to labeler A's bucket.",
    )
    parser.add_argument(
        "--B",
        required=True,
        type=int,
        metavar="N",
        help="Number of SKILL.md files assigned to labeler B's bucket.",
    )
    parser.add_argument(
        "--out-dir",
        required=True,
        metavar="DIR",
        help=(
            "Output directory; three subfolders (both/, A/, B/) "
            "will be created here."
        ),
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

    for flag, val in [("--both", args.both), ("--A", args.A), ("--B", args.B)]:
        if val <= 0:
            log.error("%s must be a positive integer, got %d", flag, val)
            sys.exit(1)

    out_dir = Path(args.out_dir).resolve()

    all_files = collect_skill_files(root)
    if not all_files:
        log.error("No SKILL.md files found under %s", root)
        sys.exit(1)

    buckets = split_into_buckets(
        all_files=all_files,
        root=root,
        out_dir=out_dir,
        n_both=args.both,
        n_A=args.A,
        n_B=args.B,
        seed=args.seed,
    )

    total = sum(len(v) for v in buckets.values())
    log.info(
        "Done. %d SKILL.md files distributed into 3 buckets under %s",
        total,
        out_dir,
    )
    for name, files in buckets.items():
        log.info("  %-8s  %d files", name, len(files))


if __name__ == "__main__":
    main()
