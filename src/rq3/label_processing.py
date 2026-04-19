from __future__ import annotations

import json
import uuid
from pathlib import Path

NORMALISE_MAP: dict[str, str] = {
    "Instructive": "instructive",
    "instructive": "instructive",
    "software design": "software-design",
    "software-design": "software-design",
    "SE workflow management": "se-workflow-management",
    "se-workflow-management": "se-workflow-management",
    "non-english": "wrong-language",
    "wrong-language": "wrong-language",
    # "references" (plural) used in some CY exports is the same concept as "reference"
    "references": "reference",
}

FILTER_SOURCE_LABELS = frozenset({
    "agent-skill",
    "wrong-language",
    "outside-scope",
})
FILTER_LABEL = "filter"

INSTRUCTION_TYPE_LABELS = (
    "commands",
    "instructive",
    "descriptive",
    "reference",
    "positive-examples",
    "negative-examples",
)

SDLC_COLLAPSE_MAP: dict[str, str] = {
    "documentation": "Documentation",
    "agent-facing": "Documentation",
    "requirements": "Requirements",
    "software-design": "Software Design",
    "code-generation": "Code Generation",
    "implementation": "Code Generation",
    "code-integration": "Code Generation",
    "program-analysis": "Code Generation",
    "software-testing": "Software Testing",
    "test-generation": "Software Testing",
    "code-quality": "Software Testing",
    "debugging": "Software Testing",
    "devops": "DevOps",
    "se-workflow-management": "DevOps",
}
SDLC_STAGE_LABELS = tuple(dict.fromkeys(SDLC_COLLAPSE_MAP.values()))

DEFAULT_EXCLUDED_FILENAMES = {
    "comparison_output.json",
}
DEFAULT_EXCLUDED_PREFIXES = (
    "kappa_",
)

PROCESSED_TAG_NAMESPACE = uuid.uuid5(
    uuid.NAMESPACE_URL,
    "https://msr-skills-md/rq3/processed-tags",
)


def normalise_label(name: str) -> str:
    stripped = name.strip()
    return NORMALISE_MAP.get(stripped, stripped)


def resolve_path(path_str: str) -> Path:
    path = Path(path_str)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def is_label_export(data: dict) -> bool:
    return isinstance(data.get("tags"), list) and isinstance(data.get("labels"), dict)


def iter_label_exports(results_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for path in sorted(results_dir.glob("*.json")):
        if path.name in DEFAULT_EXCLUDED_FILENAMES:
            continue
        if any(path.name.startswith(prefix) for prefix in DEFAULT_EXCLUDED_PREFIXES):
            continue

        data = load_json(path)
        if is_label_export(data):
            paths.append(path)

    return paths


def build_doc_label_matrix(
    data: dict,
    *,
    normalise: bool = True,
    apply_special_filter: bool = False,
) -> dict[str, set[str]]:
    tag_map: dict[str, str] = {}
    for tag in data.get("tags", []):
        name = tag.get("name", "").strip()
        if not name:
            continue
        tag_map[tag["id"]] = normalise_label(name) if normalise else name

    matrix: dict[str, set[str]] = {}
    for doc_key, doc_data in data.get("labels", {}).items():
        labels = {
            tag_map[tag_id]
            for tag_id in doc_data.get("tagIds", [])
            if tag_id in tag_map
        }
        if apply_special_filter:
            labels = process_doc_labels(labels)
        matrix[doc_key] = labels

    return matrix


def collapse_label(label: str) -> str:
    return SDLC_COLLAPSE_MAP.get(label, label)


def process_doc_labels(labels: set[str]) -> set[str]:
    if labels & FILTER_SOURCE_LABELS:
        return {FILTER_LABEL}
    return {collapse_label(label) for label in labels}


def stable_tag_id(label: str) -> str:
    return str(uuid.uuid5(PROCESSED_TAG_NAMESPACE, label))


def build_processed_export(data: dict, *, source_name: str | None = None) -> dict:
    original_doc_labels = build_doc_label_matrix(data, normalise=True, apply_special_filter=False)
    processed_doc_labels = {
        doc_key: process_doc_labels(labels)
        for doc_key, labels in sorted(original_doc_labels.items())
    }

    all_processed_labels = sorted(
        {label for labels in processed_doc_labels.values() for label in labels}
    )
    label_to_id = {label: stable_tag_id(label) for label in all_processed_labels}
    created_at = data.get("dataset", {}).get("savedAt")

    filter_source_conflicts: list[dict[str, object]] = []
    docs_changed = 0
    docs_collapsed_to_filter = 0
    filter_source_document_counts = {
        label: 0 for label in sorted(FILTER_SOURCE_LABELS)
    }

    output_labels: dict[str, dict[str, object]] = {}
    for doc_key, processed_labels in processed_doc_labels.items():
        original_labels = original_doc_labels.get(doc_key, set())
        filter_source_labels = sorted(original_labels & FILTER_SOURCE_LABELS)

        if filter_source_labels:
            docs_collapsed_to_filter += 1
            for label in filter_source_labels:
                filter_source_document_counts[label] += 1
        if processed_labels != original_labels:
            docs_changed += 1
        if len(filter_source_labels) > 1:
            filter_source_conflicts.append(
                {
                    "document": doc_key,
                    "filter_source_labels": filter_source_labels,
                }
            )

        original_doc_data = data.get("labels", {}).get(doc_key, {})
        output_doc_data: dict[str, object] = {
            "tagIds": [label_to_id[label] for label in sorted(processed_labels)],
        }
        if "updatedAt" in original_doc_data:
            output_doc_data["updatedAt"] = original_doc_data["updatedAt"]
        output_labels[doc_key] = output_doc_data

    processed_tags = [
        {
            "id": label_to_id[label],
            "name": label,
            "createdAt": created_at,
        }
        for label in all_processed_labels
    ]

    processing_counts = {
        "documents": len(original_doc_labels),
        "original_label_assignments": sum(len(labels) for labels in original_doc_labels.values()),
        "processed_label_assignments": sum(len(labels) for labels in processed_doc_labels.values()),
        "documents_changed": docs_changed,
        "documents_collapsed_to_filter": docs_collapsed_to_filter,
        "documents_with_multiple_filter_sources": len(filter_source_conflicts),
    }

    output_dataset = dict(data.get("dataset", {}))
    if source_name is not None:
        output_dataset["sourceFile"] = source_name

    return {
        "version": data.get("version", 1),
        "dataset": output_dataset,
        "processing": {
            "type": "rq3-label-processing",
            "normalisation_rules": {
                "Instructive": "instructive",
                "software design": "software-design",
                "SE workflow management": "se-workflow-management",
                "non-english": "wrong-language",
            },
            "filter_label": FILTER_LABEL,
            "filter_source_labels": list(FILTER_SOURCE_LABELS),
            "filter_source_document_counts": filter_source_document_counts,
            "sdlc_collapse_rules": {
                "Documentation": ["documentation", "agent-facing"],
                "Requirements": ["requirements"],
                "Software Design": ["software-design"],
                "Code Generation": [
                    "code-generation",
                    "implementation",
                    "code-integration",
                    "program-analysis",
                ],
                "Software Testing": [
                    "software-testing",
                    "test-generation",
                    "code-quality",
                    "debugging",
                ],
                "DevOps": ["devops", "se-workflow-management"],
            },
            "counts": processing_counts,
            "filter_source_conflicts": filter_source_conflicts,
        },
        "tags": processed_tags,
        "labels": output_labels,
    }
