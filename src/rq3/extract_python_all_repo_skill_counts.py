#!/usr/bin/env python3
"""Extract repository skill counts for repos in a processed language-all sample."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

try:
    from rq3.label_processing import FILTER_SOURCE_LABELS, SDLC_COLLAPSE_MAP, normalise_label
except ImportError:
    from label_processing import FILTER_SOURCE_LABELS, SDLC_COLLAPSE_MAP, normalise_label


DEFAULT_PYTHON_ALL = "outputs/rq3/results/processed/Python_All.json"
DEFAULT_RAW_RESULTS_DIR = "outputs/rq3/results"
DEFAULT_INSTANCES_CSV = "outputs/full_skills_instances.csv"
DEFAULT_OUT_CSV = "outputs/rq3/analysis/python_all/table_python_all_repo_skill_counts.csv"


def repo_from_artifact_id(artifact_id: str) -> str:
    """Convert an artifact id like owner__repo/path/to/skill to owner/repo."""
    repo_folder = artifact_id.split("/", 1)[0]
    if "__" not in repo_folder:
        raise ValueError(f"Cannot parse repo from artifact id: {artifact_id}")
    owner, repo = repo_folder.split("__", 1)
    return f"{owner}/{repo}"


FILTER_COLUMNS = {
    "agent-skill",
    "outside-scope",
    "wrong-language",
}


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def slugify(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def load_labeled_repo_counts(language_all_path: Path, raw_results_dir: Path, column_prefix: str) -> pd.DataFrame:
    data = load_json(language_all_path)
    labels = data.get("labels")
    if not isinstance(labels, dict):
        raise ValueError(f"{language_all_path} does not contain a labels object")

    raw_label_matrix = load_raw_label_matrix(data, raw_results_dir)
    rows = []
    for artifact_id in labels:
        raw_labels = raw_label_matrix.get(artifact_id, set())
        filter_sources = sorted(raw_labels & FILTER_SOURCE_LABELS)
        has_sdlc_label = bool(raw_labels & set(SDLC_COLLAPSE_MAP))

        row = {
            "repo": repo_from_artifact_id(artifact_id),
            f"{column_prefix}_labeled_skill_count": 1,
            f"{column_prefix}_sdlc_skill_count": int(has_sdlc_label and not filter_sources),
            f"{column_prefix}_filtered_skill_count": int(bool(filter_sources)),
            f"{column_prefix}_unclassified_count": int(not has_sdlc_label and not filter_sources),
        }
        for filter_label in sorted(FILTER_COLUMNS):
            row[f"{column_prefix}_filter_{filter_label.replace('-', '_')}_count"] = int(filter_label in filter_sources)
        rows.append(row)

    counts = pd.DataFrame(rows).groupby("repo", as_index=False).sum(numeric_only=True)
    return counts


def load_raw_label_matrix(language_all: dict, raw_results_dir: Path) -> dict[str, set[str]]:
    matrix: dict[str, set[str]] = {}
    root_name = language_all.get("dataset", {}).get("rootName", "language-all")
    source_files = language_all.get("dataset", {}).get("sourceFiles", [])
    if not source_files:
        raise ValueError(f"{root_name} JSON does not list sourceFiles in dataset metadata")

    for source_file in source_files:
        source_path = raw_results_dir / source_file
        if not source_path.is_file():
            raise FileNotFoundError(f"Missing raw source label export: {source_path}")
        source_data = load_json(source_path)
        tag_map = {
            tag["id"]: normalise_label(tag.get("name", ""))
            for tag in source_data.get("tags", [])
            if tag.get("id") and tag.get("name")
        }
        for artifact_id, doc_data in source_data.get("labels", {}).items():
            if artifact_id in matrix:
                raise ValueError(f"Duplicate artifact id across {root_name} sources: {artifact_id}")
            matrix[artifact_id] = {
                label
                for tag_id in doc_data.get("tagIds", [])
                for label in [tag_map.get(tag_id)]
                if label
            }

    missing = sorted(set(language_all.get("labels", {})) - set(matrix))
    if missing:
        preview = ", ".join(missing[:5])
        raise ValueError(f"Missing raw labels for {len(missing)} {root_name} docs: {preview}")
    return matrix


def load_global_skill_counts(instances_csv: Path) -> pd.DataFrame:
    instances = pd.read_csv(instances_csv)
    required = {"repo", "skill_path"}
    missing = sorted(required - set(instances.columns))
    if missing:
        raise ValueError(f"{instances_csv} is missing required columns: {', '.join(missing)}")

    agg_spec: dict[str, tuple[str, str]] = {"skill_count": ("skill_path", "count")}
    for column in ["mainLanguage", "stars", "forks", "commits", "contributors"]:
        if column in instances.columns:
            agg_spec[column] = (column, "first")

    return instances.groupby("repo", as_index=False).agg(**agg_spec)


def build_table(
    language_all_path: Path,
    raw_results_dir: Path,
    instances_csv: Path,
    column_prefix: str,
) -> pd.DataFrame:
    labeled_counts = load_labeled_repo_counts(language_all_path, raw_results_dir, column_prefix)
    global_counts = load_global_skill_counts(instances_csv)
    table = labeled_counts.merge(global_counts, on="repo", how="left")

    sort_cols = ["skill_count", f"{column_prefix}_sdlc_skill_count", f"{column_prefix}_labeled_skill_count", "repo"]
    ascending = [False, False, False, True]
    table = table.sort_values(sort_cols, ascending=ascending).reset_index(drop=True)
    table.insert(0, "rank", range(1, len(table) + 1))
    return table


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a repo-level skill-count table for repositories in a language-all JSON."
    )
    parser.add_argument("--python-all", default=DEFAULT_PYTHON_ALL, help="Processed Python_All JSON")
    parser.add_argument(
        "--language-all",
        default="",
        help="Processed language-all JSON. Overrides --python-all.",
    )
    parser.add_argument(
        "--column-prefix",
        default="python_all",
        help="Prefix for generated labeled/filter count columns.",
    )
    parser.add_argument(
        "--raw-results-dir",
        default=DEFAULT_RAW_RESULTS_DIR,
        help="Directory containing raw source label exports referenced by the language-all JSON",
    )
    parser.add_argument("--instances-csv", default=DEFAULT_INSTANCES_CSV, help="Skill instances CSV")
    parser.add_argument("--out-csv", default=DEFAULT_OUT_CSV, help="Output CSV path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    language_all = Path(args.language_all) if args.language_all else Path(args.python_all)
    table = build_table(
        language_all,
        Path(args.raw_results_dir),
        Path(args.instances_csv),
        slugify(args.column_prefix),
    )

    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_csv, index=False)

    print(f"Wrote {len(table)} repos to {out_csv}")
    print(table.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
