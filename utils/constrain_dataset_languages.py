#!/usr/bin/env python3
"""Filter dataset CSVs and raw_data folders to selected primary languages."""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from collections import Counter
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from filters import is_repo_excluded, load_blacklist, load_relevance_terms  # noqa: E402

SKILL_ROW_KEY = ("repo", "skill_path")
ALLOWED_MAIN_LANGUAGES = ("Python", "TypeScript")
CANONICAL_LANGUAGE_NAMES = {name.lower(): name for name in ALLOWED_MAIN_LANGUAGES}


def normalize_languages(languages: Sequence[str]) -> list[str]:
    seen: dict[str, str] = {}
    for raw in languages:
        token = str(raw).strip()
        if not token:
            continue
        canonical = CANONICAL_LANGUAGE_NAMES.get(token.lower(), token)
        key = canonical.lower()
        if key not in seen:
            seen[key] = canonical
    return list(seen.values())


def _language_allowed(value: object, allowed: set[str]) -> bool:
    return str(value or "").strip().lower() in allowed


def row_repo(row: dict[str, str]) -> str:
    return str(row.get("repo") or row.get("name") or "").strip()


def repo_filter(blacklist_path: str, relevance_terms_path: str) -> Callable[[str], bool]:
    """Return a predicate matching the blacklist + repo-name filter that RQ1 applies at load time."""
    blacklist = load_blacklist(blacklist_path)
    words = load_relevance_terms(relevance_terms_path)
    return lambda repo: is_repo_excluded(repo, blacklist, words)[0]


def filter_csv_rows(
    rows: Iterable[dict[str, str]],
    fieldnames: Sequence[str],
    languages: Sequence[str],
    exclude_repo: Optional[Callable[[str], bool]] = None,
    dedupe_skill_rows: bool = False,
) -> list[dict[str, str]]:
    allowed = {language.lower() for language in normalize_languages(languages)}
    kept: dict[object, dict[str, str]] = {}
    for index, row in enumerate(rows):
        if not _language_allowed(row.get("mainLanguage", ""), allowed):
            continue
        if exclude_repo and exclude_repo(row_repo(row)):
            continue
        key: object = index
        if dedupe_skill_rows and all(column in fieldnames for column in SKILL_ROW_KEY):
            key = tuple(str(row.get(column, "")) for column in SKILL_ROW_KEY)
            kept.pop(key, None)
        kept[key] = {name: row.get(name, "") for name in fieldnames}
    return list(kept.values())


def count_duplicate_keys(rows: Sequence[dict[str, str]], keys: Sequence[str]) -> int:
    counts: Counter[tuple[str, ...]] = Counter()
    for row in rows:
        counts[tuple(str(row.get(key, "")) for key in keys)] += 1
    return sum(count - 1 for count in counts.values() if count > 1)


def remaining_languages(raw_data_dir: Path) -> set[str]:
    if not raw_data_dir.exists():
        return set()
    return {path.name for path in raw_data_dir.iterdir() if path.is_dir()}


def snapshot_refuses_nonempty(dest: Path) -> None:
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError(f"Refusing to overwrite non-empty archive: {dest}")


def filter_csv_file(
    src: Path,
    dest: Path,
    languages: Sequence[str],
    dry_run: bool = False,
    exclude_repo: Optional[Callable[[str], bool]] = None,
    dedupe_skill_rows: bool = False,
) -> tuple[int, int]:
    with src.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {src}")
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    kept = filter_csv_rows(rows, fieldnames, languages, exclude_repo, dedupe_skill_rows)
    if not dry_run:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(kept)
    return len(kept), len(rows)


def filter_raw_data_dirs(
    src: Path,
    dest: Path,
    languages: Sequence[str],
    dry_run: bool = False,
) -> list[str]:
    selected = normalize_languages(languages)
    copied: list[str] = []
    for language in selected:
        language_src = src / language
        if not language_src.is_dir():
            continue
        copied.append(language)
        if dry_run:
            continue
        language_dest = dest / language
        if language_dest.exists():
            shutil.rmtree(language_dest)
        shutil.copytree(language_src, language_dest)
    if not dry_run:
        dest.mkdir(parents=True, exist_ok=True)
        keep = set(selected)
        for name in remaining_languages(dest):
            if name not in keep:
                shutil.rmtree(dest / name)
        leftover = remaining_languages(dest) - keep
        if leftover:
            raise ValueError(f"Disallowed primary-language folders remain: {sorted(leftover)}")
    return copied


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src-csv", action="append", default=[], help="Source CSV to filter. Repeatable.")
    parser.add_argument("--dest-csv", action="append", default=[], help="Destination CSV path matching --src-csv order.")
    parser.add_argument("--raw-data-src", default="", help="Source raw_data directory.")
    parser.add_argument("--raw-data-dest", default="", help="Destination raw_data directory.")
    parser.add_argument(
        "--languages",
        nargs="+",
        default=list(ALLOWED_MAIN_LANGUAGES),
        help="Primary languages to keep (default: Python TypeScript).",
    )
    parser.add_argument(
        "--apply-repo-filters",
        action="store_true",
        help="Also drop blacklisted and name-filtered repos (the filters RQ1 applies at load time).",
    )
    parser.add_argument("--blacklist", default=str(REPO_ROOT / "blacklist.txt"))
    parser.add_argument("--relevance-terms", default=str(REPO_ROOT / "relevance_terms.txt"))
    parser.add_argument(
        "--dedupe-skill-rows",
        action="store_true",
        help="Keep only the last row per (repo, skill_path); Stage 3 --resume re-downloads append repeat rows.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    languages = normalize_languages(args.languages)
    if len(args.src_csv) != len(args.dest_csv):
        raise ValueError("--src-csv and --dest-csv must be provided in matching pairs")

    exclude_repo = repo_filter(args.blacklist, args.relevance_terms) if args.apply_repo_filters else None
    for src_csv, dest_csv in zip(args.src_csv, args.dest_csv, strict=True):
        src = Path(src_csv)
        dest = Path(dest_csv)
        with src.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        extras = count_duplicate_keys(rows, SKILL_ROW_KEY) if rows and set(SKILL_ROW_KEY) <= rows[0].keys() else 0
        n_kept, n_total = filter_csv_file(
            src,
            dest,
            languages,
            dry_run=args.dry_run,
            exclude_repo=exclude_repo,
            dedupe_skill_rows=args.dedupe_skill_rows,
        )
        action = "would keep" if args.dry_run else "kept"
        print(f"{src} -> {dest}: {action} {n_kept}/{n_total} rows; duplicate (repo, skill_path) extras in source={extras}")

    if args.raw_data_src:
        src = Path(args.raw_data_src)
        dest = Path(args.raw_data_dest or args.raw_data_src)
        copied = filter_raw_data_dirs(src, dest, languages, dry_run=args.dry_run)
        print(f"raw_data languages {copied} from {src} -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
