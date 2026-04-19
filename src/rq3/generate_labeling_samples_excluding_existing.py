#!/usr/bin/env python3
"""Sample SKILL.md files for relabeling with strict repo exclusion.

This script mirrors the random split used by generate_labeling_samples.py:
- collect all SKILL.md files under a root
- sample without replacement using a single random draw
- partition sampled files into both/A/B buckets
- copy files while preserving paths relative to the root

Additional exclusions are applied before sampling:
- repos already present under outputs/rq3/labeling_samples/Python
- repos listed in outputs/raw_data_filtered_out/moved_repos.tsv
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
BUCKETS = ("both", "A", "B")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Randomly split SKILL.md files into relabeling buckets while "
            "excluding already-used and moved repos."
        ),
    )
    parser.add_argument(
        "--root",
        default="../../outputs/rq3/language_sample/Python",
        help="Root folder containing candidate SKILL.md files.",
    )
    parser.add_argument(
        "--exclude-root",
        default="../../outputs/rq3/labeling_samples/Python",
        help="Existing labeling-samples root used to exclude already-used repos.",
    )
    parser.add_argument(
        "--moved-repos-tsv",
        default="../../outputs/raw_data_filtered_out/moved_repos.tsv",
        help="TSV report of moved repos to exclude from sampling.",
    )
    parser.add_argument(
        "--out-dir",
        default="../../outputs/rq3/relabeling_samples/Python",
        help="Output directory where sampled SKILL.md files are copied.",
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
    return parser.parse_args(argv)


def resolve_dir(path: Path) -> Path:
    if path.exists() and path.is_dir():
        return path

    corrected = Path(str(path).replace("labeling_smaples", "labeling_samples"))
    if corrected.exists() and corrected.is_dir():
        return corrected

    raise FileNotFoundError(f"Directory does not exist: {path}")


def collect_skill_files(root: Path) -> list[Path]:
    log.info("Recursively scanning all SKILL.md files under %s", root)
    matches = [
        p
        for p in root.rglob(SKILL_FILENAME)
        if p.is_file() and p.name == SKILL_FILENAME
    ]
    log.info("Total SKILL.md files found: %d", len(matches))
    return matches


def repo_key_from_skill_file(path: Path, root: Path) -> str:
    """Map SKILL.md path to repo directory key, e.g. owner__repo."""
    rel_parts = path.relative_to(root).parts
    return rel_parts[0] if rel_parts else ""


def skill_rel_key(path: Path, root: Path) -> str:
    """Return SKILL.md path key relative to root in POSIX form."""
    return path.relative_to(root).as_posix()


def collect_existing_skill_keys(exclude_root: Path) -> set[str]:
    """Collect SKILL.md relative path keys already present in A/B/both buckets."""
    skill_keys: set[str] = set()
    for skill_file in exclude_root.rglob(SKILL_FILENAME):
        if not skill_file.is_file() or skill_file.name != SKILL_FILENAME:
            continue
        rel_parts = skill_file.relative_to(exclude_root).parts
        # Strip bucket prefix (both/A/B) to match root-relative keys in language_sample.
        if len(rel_parts) >= 2:
            skill_keys.add(Path(*rel_parts[1:]).as_posix())
    log.info("Existing SKILL.md keys in labeling samples: %d", len(skill_keys))
    return skill_keys


def collect_moved_repo_keys(moved_repos_tsv: Path) -> set[str]:
    """Collect repo directory names from moved_repos.tsv (dir_name column)."""
    if not moved_repos_tsv.is_file():
        raise FileNotFoundError(f"Moved-repos TSV does not exist: {moved_repos_tsv}")

    repo_keys: set[str] = set()
    with moved_repos_tsv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            dir_name = (row.get("dir_name") or "").strip()
            repo_name = (row.get("repo") or "").strip()

            if dir_name:
                repo_keys.add(dir_name)
            elif repo_name:
                repo_keys.add(repo_name.replace("/", "__"))

    log.info("Repo keys loaded from moved_repos.tsv: %d", len(repo_keys))
    return repo_keys


def copy_files(files: list[Path], root: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for src in files:
        rel = src.relative_to(root)
        dst = dest / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        log.debug("  copied %s -> %s", rel, dst)


def split_and_copy(
    all_files: list[Path],
    root: Path,
    out_dir: Path,
    n_both: int,
    n_A: int,
    n_B: int,
    seed: int | None,
    exclude_skill_keys: set[str],
    exclude_repo_keys: set[str],
) -> dict[str, list[Path]]:
    total = n_both + n_A + n_B
    eligible = [
        p
        for p in all_files
        if skill_rel_key(p, root) not in exclude_skill_keys
        and repo_key_from_skill_file(p, root) not in exclude_repo_keys
    ]

    if total > len(eligible):
        log.error(
            "Requested total (%d) exceeds eligible SKILL.md count (%d) after exclusion.",
            total,
            len(eligible),
        )
        sys.exit(1)

    rng = random.Random(seed)
    sampled = rng.sample(eligible, total)

    buckets: dict[str, list[Path]] = {
        "both": sampled[:n_both],
        "A": sampled[n_both : n_both + n_A],
        "B": sampled[n_both + n_A :],
    }

    for bucket, files in buckets.items():
        dest_bucket = out_dir / bucket
        log.info("Writing %d files -> %s", len(files), dest_bucket)
        copy_files(files, root, dest_bucket)

    return buckets


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    root = resolve_dir(Path(args.root).resolve())
    exclude_root = resolve_dir(Path(args.exclude_root).resolve())
    moved_repos_tsv = Path(args.moved_repos_tsv).resolve()
    out_dir = Path(args.out_dir).resolve()

    for flag, val in [("--both", args.both), ("--A", args.A), ("--B", args.B)]:
        if val <= 0:
            log.error("%s must be a positive integer, got %d", flag, val)
            sys.exit(1)

    all_files = collect_skill_files(root)
    if not all_files:
        log.error("No SKILL.md files found under %s", root)
        sys.exit(1)

    exclude_skill_keys = collect_existing_skill_keys(exclude_root)
    exclude_repo_keys = collect_moved_repo_keys(moved_repos_tsv)
    log.info("Total excluded SKILL.md keys from labeling samples: %d", len(exclude_skill_keys))
    log.info("Total excluded repo keys from moved TSV: %d", len(exclude_repo_keys))

    buckets = split_and_copy(
        all_files=all_files,
        root=root,
        out_dir=out_dir,
        n_both=args.both,
        n_A=args.A,
        n_B=args.B,
        seed=args.seed,
        exclude_skill_keys=exclude_skill_keys,
        exclude_repo_keys=exclude_repo_keys,
    )

    total = sum(len(v) for v in buckets.values())
    log.info("Done. %d SKILL.md files distributed into 3 buckets under %s", total, out_dir)
    for bucket, files in buckets.items():
        log.info("  %-8s  %d files", bucket, len(files))


if __name__ == "__main__":
    main()
