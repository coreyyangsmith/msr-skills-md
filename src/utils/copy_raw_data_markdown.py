#!/usr/bin/env python3
"""Copy only files named ``SKILL.md`` from a raw_data tree into raw_data_skills."""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

SKILL_FILENAME = "SKILL.md"


def copy_markdown_files(src: Path, dest: Path) -> int:
    """Copy every ``SKILL.md`` file under *src* into *dest*, preserving relative paths."""
    src = src.resolve()
    dest = dest.resolve()
    if not src.is_dir():
        raise FileNotFoundError(f"Directory does not exist: {src}")
    if dest == src or dest.is_relative_to(src):
        raise ValueError(f"Destination {dest} must not be inside source {src}")

    copied = 0
    for path in src.rglob(SKILL_FILENAME):
        if not path.is_file() or path.name != SKILL_FILENAME:
            continue
        out = dest / path.relative_to(src)
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
        copied += 1
    return copied


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Copy only SKILL.md files from raw_data into a parallel raw_data_skills tree.",
    )
    parser.add_argument(
        "--raw-data-dir",
        default="outputs/raw_data",
        help="Source raw_data directory (default: outputs/raw_data).",
    )
    parser.add_argument(
        "--out-dir",
        default="outputs/raw_data_skills",
        help="Destination directory (default: outputs/raw_data_skills).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    src = Path(args.raw_data_dir)
    dest = Path(args.out_dir)
    try:
        copied = copy_markdown_files(src, dest)
    except (FileNotFoundError, ValueError) as exc:
        log.error("%s", exc)
        return 1
    log.info("Copied %d SKILL.md files from %s to %s", copied, src.resolve(), dest.resolve())
    print(copied)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
