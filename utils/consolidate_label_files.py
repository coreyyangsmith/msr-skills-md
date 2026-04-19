#!/usr/bin/env python3
"""Merge original label JSON exports with relabel exports into Final_Labels files.

See plan: outputs/rq3/results consolidation (CY/MV × A/B/both).
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "outputs" / "rq3" / "results"
CSV_PATH = REPO_ROOT / "outputs" / "raw_data_filtered_out" / "removed_repos_in_python_labeling_samples.csv"

PAIRS: list[dict[str, str]] = [
    {
        "original": "2026-04-06_CY_Labels_A_Python.json",
        "relabel": "2026-04-19_CY_Relabels_A_Python.json",
        "output": "2026-04-19_CY_Final_Labels_A_Python.json",
        "bucket": "A",
        "tag_mode": "cy",  # dedupe tags by name (case-insensitive)
    },
    {
        "original": "2026-04-02_CY_Labels_Both_Python.json",
        "relabel": "2026-04-19_CY_Relabels_Both_Python.json",
        "output": "2026-04-19_CY_Final_Labels_Both_Python.json",
        "bucket": "both",
        "tag_mode": "cy",
    },
    {
        "original": "2026-04-06_MV_Labels_B_Python.json",
        "relabel": "2026-04-19_MV_Relabels_B_Python.json",
        "output": "2026-04-19_MV_Final_Labels_B_Python.json",
        "bucket": "B",
        "tag_mode": "mv",
    },
    {
        "original": "2026-03-31_MV_Labels_Both_Python.json",
        "relabel": "2026-04-19-MV_Relabels_Both_Python.json",
        "output": "2026-04-19_MV_Final_Labels_Both_Python.json",
        "bucket": "both",
        "tag_mode": "mv",
    },
]


def load_excluded_repo_dirs(csv_path: Path) -> set[tuple[str, str]]:
    """Return {(subfolder, owner__repo_dir_name), ...} for agent-filtered repos."""
    excluded: set[tuple[str, str]] = set()
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            repo = (row.get("repo") or "").strip()
            sub = (row.get("subfolder") or "").strip()
            if not repo or not sub:
                continue
            dir_name = repo.replace("/", "__")
            excluded.add((sub, dir_name))
    return excluded


def label_key_repo_dir(label_key: str) -> str:
    """First path segment is owner__repo."""
    parts = label_key.replace("\\", "/").split("/", 1)
    return parts[0] if parts else ""


def should_exclude_label_key(
    label_key: str,
    bucket: str,
    excluded: set[tuple[str, str]],
) -> bool:
    d = label_key_repo_dir(label_key)
    return (bucket, d) in excluded


def build_tag_union_cy(
    original_tags: list[dict[str, Any]],
    relabel_tags: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Deduplicate by tag name (case-insensitive). Original wins for id/createdAt."""
    unified: list[dict[str, Any]] = [dict(t) for t in original_tags]
    name_to_canonical_id: dict[str, str] = {}
    for t in unified:
        name_to_canonical_id[t["name"].lower()] = t["id"]

    relabel_id_to_canonical: dict[str, str] = {}

    for t in relabel_tags:
        tid = t["id"]
        name_lower = t["name"].lower()
        if name_lower in name_to_canonical_id:
            relabel_id_to_canonical[tid] = name_to_canonical_id[name_lower]
        else:
            unified.append(dict(t))
            name_to_canonical_id[name_lower] = tid
            relabel_id_to_canonical[tid] = tid

    return unified, relabel_id_to_canonical


def build_tag_union_mv(
    original_tags: list[dict[str, Any]],
    relabel_tags: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Union by tag id; MV relabels reuse the same id namespace."""
    seen_ids: set[str] = {t["id"] for t in original_tags}
    unified: list[dict[str, Any]] = [dict(t) for t in original_tags]
    relabel_id_to_canonical: dict[str, str] = {}

    for t in relabel_tags:
        tid = t["id"]
        relabel_id_to_canonical[tid] = tid
        if tid not in seen_ids:
            unified.append(dict(t))
            seen_ids.add(tid)

    return unified, relabel_id_to_canonical


def translate_tag_ids(
    tag_ids: list[str],
    relabel_id_to_canonical: dict[str, str],
) -> list[str]:
    out: list[str] = []
    for tid in tag_ids:
        if tid not in relabel_id_to_canonical:
            raise KeyError(f"Unknown tag id in relabel entry: {tid}")
        canon = relabel_id_to_canonical[tid]
        if canon not in out:
            out.append(canon)
    return sorted(out)


def merge_label_entries(
    rel: dict[str, Any],
    relabel_id_to_canonical: dict[str, str],
) -> dict[str, Any]:
    tag_ids = translate_tag_ids(rel.get("tagIds", []), relabel_id_to_canonical)
    return {"tagIds": tag_ids, "updatedAt": rel.get("updatedAt", "")}


def consolidate_pair(
    pair: dict[str, str],
    excluded: set[tuple[str, str]],
) -> dict[str, Any]:
    bucket = pair["bucket"]
    tag_mode = pair["tag_mode"]

    orig_path = RESULTS_DIR / pair["original"]
    rel_path = RESULTS_DIR / pair["relabel"]

    with orig_path.open(encoding="utf-8") as f:
        original = json.load(f)
    with rel_path.open(encoding="utf-8") as f:
        relabel = json.load(f)

    if tag_mode == "cy":
        unified_tags, relabel_id_to_canonical = build_tag_union_cy(
            original["tags"], relabel["tags"]
        )
    elif tag_mode == "mv":
        unified_tags, relabel_id_to_canonical = build_tag_union_mv(
            original["tags"], relabel["tags"]
        )
    else:
        raise ValueError(f"Unknown tag_mode: {tag_mode}")

    orig_labels: dict[str, Any] = original.get("labels", {})
    merged: dict[str, Any] = {}

    for key, entry in orig_labels.items():
        if should_exclude_label_key(key, bucket, excluded):
            continue
        merged[key] = dict(entry)

    rel_labels = relabel.get("labels", {})
    for key, entry in rel_labels.items():
        new_entry = merge_label_entries(entry, relabel_id_to_canonical)
        if key in merged:
            old_ids = set(merged[key].get("tagIds", []))
            new_ids = set(new_entry["tagIds"])
            merged[key]["tagIds"] = sorted(old_ids | new_ids)
            if new_entry.get("updatedAt", "") > merged[key].get("updatedAt", ""):
                merged[key]["updatedAt"] = new_entry["updatedAt"]
        else:
            merged[key] = new_entry

    saved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    return {
        "version": 1,
        "dataset": {
            "rootName": original["dataset"]["rootName"],
            "savedAt": saved_at,
            "totalFiles": len(merged),
        },
        "tags": unified_tags,
        "labels": merged,
    }


def main() -> None:
    if not CSV_PATH.is_file():
        raise FileNotFoundError(f"Missing CSV: {CSV_PATH}")

    excluded = load_excluded_repo_dirs(CSV_PATH)

    for pair in PAIRS:
        out_name = pair["output"]
        out_path = RESULTS_DIR / out_name
        result = consolidate_pair(pair, excluded)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8", newline="\n") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
        print(f"Wrote {out_path} ({result['dataset']['totalFiles']} labels)")


if __name__ == "__main__":
    main()
