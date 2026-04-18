#!/usr/bin/env python3
"""Collect normalized SKILL.md documents from raw_data for RQ2 analyses."""

from __future__ import annotations

import argparse
import json
import logging
import re
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

log = logging.getLogger(__name__)

HEADING_LEVEL_RE = re.compile(r"^(#{1,6})\s+\S")
UNORDERED_LIST_RE = re.compile(r"^\s*[-*+]\s+")
ORDERED_LIST_RE = re.compile(r"^\s*\d+\.\s+")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
FENCED_CODE_RE = re.compile(r"```(?:[^\n`]*)\n[\s\S]*?\n```", re.DOTALL)
FENCED_CODE_WITH_INFO_PATTERN = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)
WORD_RE = re.compile(r"\b\w+\b")
FILE_PATH_PATTERN = re.compile(
    r"\b(?:\.{0,2}/)?[\w\-./]+\.(?:py|js|ts|tsx|jsx|sh|yaml|yml|json|md|txt|css|html|xml|toml)\b"
)
URL_PATTERN = re.compile(r"https?://[^\s)]+")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^\]]+\]\((https?://[^\)]+)\)")
DISALLOWED_FILE_REFERENCE_NAMES = {"node.js", "next.js"}

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect SKILL.md documents from raw_data into a normalized dataset.")
    parser.add_argument(
        "--raw-data-dir",
        default="../../outputs/raw_data",
        help="Root raw_data directory (default: outputs/raw_data)",
    )
    parser.add_argument(
        "--out-jsonl",
        default="../../outputs/rq2/skill_documents.jsonl",
        help="Output JSONL path for collected SKILL.md documents",
    )
    parser.add_argument(
        "--out-stats-json",
        default="../../outputs/rq2/skill_documents_stats.json",
        help="Output JSON path for collection statistics",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )
    return parser.parse_args(argv)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def collect_markdown_structure(text: str) -> dict[str, Any]:
    lines = text.splitlines()

    list_blocks = 0
    in_list_block = False
    for line in lines:
        is_list_line = bool(UNORDERED_LIST_RE.match(line) or ORDERED_LIST_RE.match(line))
        if is_list_line and not in_list_block:
            list_blocks += 1
            in_list_block = True
        elif not is_list_line:
            in_list_block = False

    has_inline_code = bool(INLINE_CODE_RE.search(text))
    has_fenced_code = bool(FENCED_CODE_RE.search(text))
    inline_code_count = len(INLINE_CODE_RE.findall(text))
    fenced_code_count = len(FENCED_CODE_RE.findall(text))
    code_count = inline_code_count + fenced_code_count

    section_word_counts: list[int] = []
    current_section_lines: list[str] = []
    heading_seen = False
    for line in lines:
        if HEADING_LEVEL_RE.match(line):
            if heading_seen:
                section_text = "\n".join(current_section_lines).strip()
                if section_text:
                    section_word_counts.append(len(WORD_RE.findall(section_text)))
            current_section_lines = []
            heading_seen = True
        else:
            if heading_seen:
                current_section_lines.append(line)

    if heading_seen:
        section_text = "\n".join(current_section_lines).strip()
        if section_text:
            section_word_counts.append(len(WORD_RE.findall(section_text)))

    heading_levels: list[int] = []
    for line in lines:
        match = HEADING_LEVEL_RE.match(line)
        if match:
            heading_levels.append(len(match.group(1)))

    heading_level_counts = Counter(heading_levels)
    heading_h1_count = heading_level_counts[1]
    heading_h2_count = heading_level_counts[2]
    heading_h3_count = heading_level_counts[3]
    heading_h4_count = heading_level_counts[4]
    heading_h5_count = heading_level_counts[5]
    heading_h6_count = heading_level_counts[6]
    most_common_level = None
    if heading_level_counts:
        max_count = max(heading_level_counts.values())
        candidates = [level for level, count in heading_level_counts.items() if count == max_count]
        most_common_level = min(candidates)

    return {
        "heading_h1_count": heading_h1_count,
        "heading_h2_count": heading_h2_count,
        "heading_h3_count": heading_h3_count,
        "heading_h4_count": heading_h4_count,
        "heading_h5_count": heading_h5_count,
        "heading_h6_count": heading_h6_count,
        "heading_count": len(heading_levels),
        "avg_heading_depth": (sum(heading_levels) / len(heading_levels)) if heading_levels else 0.0,
        "most_common_heading_level": most_common_level,
        "max_heading_depth": max(heading_levels) if heading_levels else 0,
        "section_count": len(section_word_counts),
        "avg_section_length": (sum(section_word_counts) / len(section_word_counts)) if section_word_counts else 0.0,
        "max_section_length": max(section_word_counts) if section_word_counts else 0,
        "list_count": list_blocks,
        "has_code": has_inline_code or has_fenced_code,
        "has_inline_code": has_inline_code,
        "has_fenced_code": has_fenced_code,
        "inline_code_count": inline_code_count,
        "fenced_code_count": fenced_code_count,
        "code_count": code_count,
    }


def normalize_fenced_code_language(info_string: str) -> str | None:
    token = info_string.strip()
    if not token:
        return None

    # Keep only the first token in case the info string has extra metadata.
    token = token.split()[0].strip()
    token = token.lstrip("{.").rstrip("}").strip().lower()
    token = token.strip("[]()")
    if not token:
        return None

    alias_map = {
        "sh": "bash",
        "shell": "bash",
        "zsh": "bash",
        "console": "bash",
        "shellscript": "bash",
        "py": "python",
        "js": "javascript",
        "ts": "typescript",
        "yml": "yaml",
        "ps1": "powershell",
        "pwsh": "powershell",
        "cmd": "batch",
        "bat": "batch",
    }
    return alias_map.get(token, token)


def extract_fenced_code_languages(text: str) -> tuple[list[str], int]:
    matches = FENCED_CODE_WITH_INFO_PATTERN.findall(text)
    languages: list[str] = []
    for info_string, _ in matches:
        language = normalize_fenced_code_language(info_string)
        if language:
            languages.append(language)
    return languages, len(matches)


def extract_file_paths(text: str) -> list[str]:
    paths = FILE_PATH_PATTERN.findall(text)
    filtered_paths = [
        path
        for path in paths
        if Path(path).name.lower() not in DISALLOWED_FILE_REFERENCE_NAMES
    ]
    return sorted(set(filtered_paths))


def extract_urls(text: str) -> list[str]:
    urls = URL_PATTERN.findall(text)
    md_links = MARKDOWN_LINK_PATTERN.findall(text)
    return sorted(set(urls + md_links))


def classify_reference(path: str) -> str:
    path_lower = path.lower()

    if "scripts/" in path_lower:
        return "script"
    if "references/" in path_lower:
        return "documentation"
    if "assets/" in path_lower:
        return "asset"

    if path_lower.endswith((".sh", ".py", ".js", ".ts", ".tsx", ".jsx")):
        return "script"
    if path_lower.endswith(".md"):
        return "documentation"
    if path_lower.endswith((".json", ".yaml", ".yml", ".txt", ".css", ".html", ".xml", ".toml")):
        return "asset"
    return "other"


def extract_and_classify_references(text: str) -> list[dict[str, str]]:
    paths = extract_file_paths(text)
    urls = extract_urls(text)
    file_refs = [{"path": path, "type": classify_reference(path)} for path in paths]
    url_refs = [{"path": url, "type": "url"} for url in urls]
    return file_refs + url_refs


def summarize_references(refs: list[dict[str, str]]) -> dict[str, int]:
    counter = Counter(ref["type"] for ref in refs)
    return {
        "num_references": len(refs),
        "num_scripts": counter["script"],
        "num_docs": counter["documentation"],
        "num_assets": counter["asset"],
        "num_urls": counter["url"],
        "num_other": counter["other"],
    }


def _build_document(path: Path, raw_data_dir: Path) -> dict[str, Any] | None:
    try:
        relative_to_raw = path.relative_to(raw_data_dir)
    except ValueError:
        return None

    parts = relative_to_raw.parts
    if len(parts) < 3:
        return None

    language = parts[0]
    repo = parts[1]
    relative_path = Path(*parts[2:]).as_posix()

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        log.warning("Skipping unreadable file %s: %s", path, exc)
        return None

    structure = collect_markdown_structure(text)
    references = extract_and_classify_references(text)
    reference_summary = summarize_references(references)

    return {
        "language": language,
        "repo": repo,
        "relative_path": relative_path,
        "full_path": str(path.resolve()),
        "text": text,
        "file_name": path.name,
        "structure": structure,
        "references": {
            "items": references,
            "summary": reference_summary,
        },
    }


def collect_skill_documents(raw_data_dir: Path) -> list[dict[str, Any]]:
    skill_files = sorted(path for path in raw_data_dir.rglob("SKILL.md") if path.is_file())
    log.info("Found %d SKILL.md files in %s", len(skill_files), raw_data_dir)

    documents: list[dict[str, Any]] = []
    skipped = 0
    for path in skill_files:
        doc = _build_document(path, raw_data_dir)
        if doc is None:
            skipped += 1
            continue
        documents.append(doc)

    if skipped:
        log.info("Skipped %d files due to unexpected path layout or read errors", skipped)
    return documents


def compute_stats(documents: list[dict[str, Any]]) -> dict[str, Any]:
    by_language = Counter(doc["language"] for doc in documents)
    by_repo = Counter(doc["repo"] for doc in documents)

    char_counts = [len(doc["text"]) for doc in documents]
    line_counts = [doc["text"].count("\n") + 1 for doc in documents]
    word_counts = [len(doc["text"].split()) for doc in documents]

    h1_total = sum(int(doc["structure"]["heading_h1_count"]) for doc in documents)
    h2_total = sum(int(doc["structure"]["heading_h2_count"]) for doc in documents)
    h3_total = sum(int(doc["structure"]["heading_h3_count"]) for doc in documents)
    h4_total = sum(int(doc["structure"]["heading_h4_count"]) for doc in documents)
    h5_total = sum(int(doc["structure"]["heading_h5_count"]) for doc in documents)
    h6_total = sum(int(doc["structure"]["heading_h6_count"]) for doc in documents)
    h1_per_doc = [int(doc["structure"]["heading_h1_count"]) for doc in documents]
    h2_per_doc = [int(doc["structure"]["heading_h2_count"]) for doc in documents]
    h3_per_doc = [int(doc["structure"]["heading_h3_count"]) for doc in documents]
    h4_per_doc = [int(doc["structure"]["heading_h4_count"]) for doc in documents]
    h5_per_doc = [int(doc["structure"]["heading_h5_count"]) for doc in documents]
    h6_per_doc = [int(doc["structure"]["heading_h6_count"]) for doc in documents]
    avg_heading_depth_per_doc = [float(doc["structure"]["avg_heading_depth"]) for doc in documents]
    avg_section_length_per_doc = [float(doc["structure"]["avg_section_length"]) for doc in documents]
    list_count_per_doc = [int(doc["structure"]["list_count"]) for doc in documents]
    heading_total = sum(int(doc["structure"]["heading_count"]) for doc in documents)
    list_total = sum(int(doc["structure"]["list_count"]) for doc in documents)
    docs_with_code = sum(1 for doc in documents if bool(doc["structure"]["has_code"]))
    code_count_per_doc = [int(doc["structure"].get("code_count", 0)) for doc in documents]
    inline_code_count_per_doc = [int(doc["structure"].get("inline_code_count", 0)) for doc in documents]
    fenced_code_count_per_doc = [int(doc["structure"].get("fenced_code_count", 0)) for doc in documents]
    section_total = sum(int(doc["structure"]["section_count"]) for doc in documents)
    section_length_sum = sum(
        float(doc["structure"]["avg_section_length"]) * int(doc["structure"]["section_count"])
        for doc in documents
    )
    section_max_values = [int(doc["structure"]["max_section_length"]) for doc in documents]
    heading_depth_sum = sum(
        float(doc["structure"]["avg_heading_depth"]) * int(doc["structure"]["heading_count"])
        for doc in documents
    )
    heading_level_counter: Counter[int] = Counter()
    docs_with_headings = 0
    max_depth_values = [int(doc["structure"]["max_heading_depth"]) for doc in documents]
    for doc in documents:
        heading_count = int(doc["structure"]["heading_count"])
        if heading_count > 0:
            docs_with_headings += 1
    for doc in documents:
        text = doc["text"]
        for line in text.splitlines():
            match = HEADING_LEVEL_RE.match(line)
            if match:
                heading_level_counter[len(match.group(1))] += 1

    most_common_level = None
    if heading_level_counter:
        max_count = max(heading_level_counter.values())
        candidates = [level for level, count in heading_level_counter.items() if count == max_count]
        most_common_level = min(candidates)
    ref_type_counter: Counter[str] = Counter()
    total_references = 0
    docs_with_references = 0
    reference_count_per_doc: list[int] = []
    for doc in documents:
        ref_items = list(doc.get("references", {}).get("items", []))
        reference_count_per_doc.append(len(ref_items))
        if ref_items:
            docs_with_references += 1
        total_references += len(ref_items)
        ref_type_counter.update(ref.get("type", "other") for ref in ref_items)

    # Separate URL references from file references
    url_paths = Counter(
        ref.get("path")
        for doc in documents
        for ref in doc.get("references", {}).get("items", [])
        if ref.get("type") == "url" and ref.get("path")
    )
    file_paths = Counter(
        ref.get("path")
        for doc in documents
        for ref in doc.get("references", {}).get("items", [])
        if ref.get("type") != "url" and ref.get("path")
    )

    fenced_language_counter: Counter[str] = Counter()
    fenced_blocks_total = 0
    fenced_blocks_with_language = 0
    docs_with_fenced_code = 0
    for doc in documents:
        languages, fenced_block_count = extract_fenced_code_languages(doc["text"])
        if fenced_block_count > 0:
            docs_with_fenced_code += 1
        fenced_blocks_total += fenced_block_count
        fenced_blocks_with_language += len(languages)
        if languages:
            fenced_language_counter.update(languages)

    total_docs = len(documents)
    stats: dict[str, Any] = {
        "total_documents": total_docs,
        "unique_languages": len(by_language),
        "unique_repos": len(by_repo),
        "documents_by_language": dict(sorted(by_language.items())),
        "top_20_repos_by_skill_file_count": by_repo.most_common(20),
        "text_length": {
            "total_chars": sum(char_counts),
            "avg_chars": (sum(char_counts) / total_docs) if total_docs else 0.0,
            "total_words": sum(word_counts),
            "avg_words": (sum(word_counts) / total_docs) if total_docs else 0.0,
            "median_words": median(word_counts) if word_counts else 0.0,
            "avg_lines": (sum(line_counts) / total_docs) if total_docs else 0.0,
            "median_lines": median(line_counts) if line_counts else 0.0,
        },
        "markdown_structure": {
            "heading_h1_total": h1_total,
            "heading_h2_total": h2_total,
            "heading_h3_total": h3_total,
            "heading_h4_total": h4_total,
            "heading_h5_total": h5_total,
            "heading_h6_total": h6_total,
            "heading_total": heading_total,
            "list_total": list_total,
            "avg_h1_per_doc": (h1_total / total_docs) if total_docs else 0.0,
            "avg_h2_per_doc": (h2_total / total_docs) if total_docs else 0.0,
            "avg_h3_per_doc": (h3_total / total_docs) if total_docs else 0.0,
            "avg_h4_per_doc": (h4_total / total_docs) if total_docs else 0.0,
            "avg_h5_per_doc": (h5_total / total_docs) if total_docs else 0.0,
            "avg_h6_per_doc": (h6_total / total_docs) if total_docs else 0.0,
            "median_h1_per_doc": median(h1_per_doc) if h1_per_doc else 0.0,
            "median_h2_per_doc": median(h2_per_doc) if h2_per_doc else 0.0,
            "median_h3_per_doc": median(h3_per_doc) if h3_per_doc else 0.0,
            "median_h4_per_doc": median(h4_per_doc) if h4_per_doc else 0.0,
            "median_h5_per_doc": median(h5_per_doc) if h5_per_doc else 0.0,
            "median_h6_per_doc": median(h6_per_doc) if h6_per_doc else 0.0,
            "avg_heading_depth": (heading_depth_sum / heading_total) if heading_total else 0.0,
            "median_heading_depth": median(avg_heading_depth_per_doc) if avg_heading_depth_per_doc else 0.0,
            "most_common_level": most_common_level,
            "max_depth_overall": max(max_depth_values) if max_depth_values else 0,
            "section_total": section_total,
            "avg_section_length": (section_length_sum / section_total) if section_total else 0.0,
            "median_section_length": median(avg_section_length_per_doc) if avg_section_length_per_doc else 0.0,
            "max_section_length": max(section_max_values) if section_max_values else 0,
            "median_max_section_length": median(section_max_values) if section_max_values else 0.0,
            "docs_with_headings": docs_with_headings,
            "docs_without_headings": total_docs - docs_with_headings,
            "avg_lists_per_doc": (list_total / total_docs) if total_docs else 0.0,
            "median_lists_per_doc": median(list_count_per_doc) if list_count_per_doc else 0.0,
            "docs_with_code": docs_with_code,
            "docs_without_code": total_docs - docs_with_code,
            "code_usage_rate": (docs_with_code / total_docs) if total_docs else 0.0,
            "avg_code_per_doc": (sum(code_count_per_doc) / total_docs) if total_docs else 0.0,
            "median_code_per_doc": median(code_count_per_doc) if code_count_per_doc else 0.0,
            "median_inline_code_per_doc": median(inline_code_count_per_doc) if inline_code_count_per_doc else 0.0,
            "median_fenced_code_blocks_per_doc": median(fenced_code_count_per_doc) if fenced_code_count_per_doc else 0.0,
        },
        "fenced_code_languages": {
            "total_fenced_code_blocks": fenced_blocks_total,
            "fenced_code_blocks_with_language": fenced_blocks_with_language,
            "fenced_code_blocks_without_language": fenced_blocks_total - fenced_blocks_with_language,
            "docs_with_fenced_code_blocks": docs_with_fenced_code,
            "docs_without_fenced_code_blocks": total_docs - docs_with_fenced_code,
            "unique_fenced_code_languages": len(fenced_language_counter),
            "top_20_fenced_code_languages": fenced_language_counter.most_common(20),
            "all_fenced_code_language_counts": dict(sorted(fenced_language_counter.items())),
        },
        "references": {
            "total_references": total_references,
            "unique_references": len(
                {
                    ref.get("path")
                    for doc in documents
                    for ref in doc.get("references", {}).get("items", [])
                    if ref.get("path")
                }
            ),
            "docs_with_references": docs_with_references,
            "docs_without_references": total_docs - docs_with_references,
            "reference_usage_rate": (docs_with_references / total_docs) if total_docs else 0.0,
            "avg_references_per_doc": (sum(reference_count_per_doc) / total_docs) if total_docs else 0.0,
            "median_references_per_doc": median(reference_count_per_doc) if reference_count_per_doc else 0.0,
            "num_scripts": ref_type_counter["script"],
            "num_docs": ref_type_counter["documentation"],
            "num_assets": ref_type_counter["asset"],
            "num_urls": ref_type_counter["url"],
            "num_other": ref_type_counter["other"],
            "top_50_file_reference_paths": file_paths.most_common(50),
            "top_50_url_references": url_paths.most_common(50),
        },
    }
    return stats


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    raw_data_dir = Path(args.raw_data_dir)
    if not raw_data_dir.exists() or not raw_data_dir.is_dir():
        raise FileNotFoundError(f"Raw data directory not found: {raw_data_dir}")

    documents = collect_skill_documents(raw_data_dir)
    stats = compute_stats(documents)

    out_jsonl = Path(args.out_jsonl)
    out_stats_json = Path(args.out_stats_json)
    write_jsonl(out_jsonl, documents)
    write_json(out_stats_json, stats)

    print(f"Collected {len(documents)} SKILL.md documents")
    print(f"- dataset: {out_jsonl.resolve()}")
    print(f"- stats:   {out_stats_json.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
