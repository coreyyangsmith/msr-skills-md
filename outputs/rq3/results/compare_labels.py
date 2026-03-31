import argparse
import json
from collections import Counter
from pathlib import Path


def load_json(path):
    with open(path, "r") as f:
        return json.load(f)


def write_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def map_tag_id_to_name(tags):
    return {tag["id"]: tag["name"] for tag in tags}


def compare_tags(tags1, tags2):
    names1 = {t["name"] for t in tags1}
    names2 = {t["name"] for t in tags2}
    return {
        "added_tags": sorted(names2 - names1),
        "removed_tags": sorted(names1 - names2),
    }


def count_tag_occurrences(labels, tag_map):
    counts = Counter()
    for doc_data in labels.values():
        for tag_id in set(doc_data.get("tagIds", [])):  # once per document
            tag_name = tag_map.get(tag_id, f"<unknown:{tag_id}>")
            counts[tag_name] += 1
    return dict(sorted(counts.items()))


def compare_labels(data1, data2):
    labels1 = data1["labels"]
    labels2 = data2["labels"]

    tag_map1 = map_tag_id_to_name(data1["tags"])
    tag_map2 = map_tag_id_to_name(data2["tags"])

    docs1 = set(labels1.keys())
    docs2 = set(labels2.keys())
    common_docs = docs1 & docs2

    changed_labels = []
    same_count = 0
    different_count = 0

    for doc in sorted(common_docs):
        tags1 = {tag_map1.get(t, f"<unknown:{t}>") for t in labels1[doc].get("tagIds", [])}
        tags2 = {tag_map2.get(t, f"<unknown:{t}>") for t in labels2[doc].get("tagIds", [])}

        if tags1 != tags2:
            different_count += 1
            changed_labels.append(
                {
                    "document": doc,
                    "common": sorted(tags1 & tags2),
                    "removed": sorted(tags1 - tags2),
                    "added": sorted(tags2 - tags1),
                }
            )
        else:
            same_count += 1

    return {
        "document_differences": {
            "added_docs": sorted(docs2 - docs1),
            "removed_docs": sorted(docs1 - docs2),
        },
        "label_match_summary": {
            "common_docs": len(common_docs),
            "same_labels": same_count,
            "different_labels": different_count,
        },
        "changed_labels": changed_labels,
        "tag_occurrence_counts": {
            "file1": count_tag_occurrences(labels1, tag_map1),
            "file2": count_tag_occurrences(labels2, tag_map2),
        },
    }


def resolve_path(base_dir, p):
    p = Path(p)
    return p if p.is_absolute() else (base_dir / p).resolve()


def main(file1, file2, output):
    base_dir = Path(__file__).resolve().parent
    file1_path = resolve_path(base_dir, file1)
    file2_path = resolve_path(base_dir, file2)
    output_path = resolve_path(base_dir, output)

    data1 = load_json(file1_path)
    data2 = load_json(file2_path)

    report = {
        "file1": str(file1_path),
        "file2": str(file2_path),
        "tag_differences": compare_tags(data1["tags"], data2["tags"]),
        **compare_labels(data1, data2),
    }

    write_json(output_path, report)
    print(f"Wrote comparison JSON: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare two label JSON files.")
    parser.add_argument("file1", help="Path to baseline JSON file")
    parser.add_argument("file2", help="Path to comparison JSON file")
    parser.add_argument(
        "-o",
        "--output",
        default="comparison_output.json",
        help="Output JSON file path (default: comparison_output.json)",
    )
    args = parser.parse_args()

    main(args.file1, args.file2, args.output)