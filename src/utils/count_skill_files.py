#!/usr/bin/env python3
"""Count SKILL.md files under a raw-data directory."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

log = logging.getLogger(__name__)

SKILL_FILENAME = "SKILL.md"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Count all SKILL.md files recursively under raw_data.",
    )
    parser.add_argument(
        "--raw-data-dir",
        default="../../outputs/raw_data",
        help="Root raw_data directory to scan recursively (default: outputs/raw_data).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return parser.parse_args(argv)


def count_skill_files(raw_data_dir: Path) -> int:
    if not raw_data_dir.is_dir():
        raise FileNotFoundError(f"Directory does not exist: {raw_data_dir}")

    return sum(
        1
        for path in raw_data_dir.rglob(SKILL_FILENAME)
        if path.is_file() and path.name == SKILL_FILENAME
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )

    raw_data_dir = Path(args.raw_data_dir).resolve()

    try:
        total = count_skill_files(raw_data_dir)
    except FileNotFoundError as exc:
        log.error("%s", exc)
        return 1

    print(total)
    log.info("Counted %d SKILL.md files under %s", total, raw_data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
