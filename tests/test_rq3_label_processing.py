from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq3.analyze_processed_labels import instruction_sdlc_matrix, split_filtered_docs
from rq3.label_processing import build_processed_export, process_doc_labels


class TestRq3LabelProcessing(unittest.TestCase):
    def test_process_doc_labels_collapses_filter_sources_to_filter(self):
        self.assertEqual(
            process_doc_labels({"wrong-language", "outside-scope", "commands"}),
            {"filter"},
        )
        self.assertEqual(
            process_doc_labels({"outside-scope", "agent-skill", "reference"}),
            {"filter"},
        )
        self.assertEqual(
            process_doc_labels({"agent-skill", "commands"}),
            {"filter"},
        )

    def test_build_processed_export_normalises_and_collapses_labels(self):
        data = {
            "version": 1,
            "dataset": {"rootName": "both", "savedAt": "2026-04-06T12:00:00Z"},
            "tags": [
                {"id": "1", "name": "Instructive"},
                {"id": "2", "name": "software design"},
                {"id": "3", "name": "agent-facing"},
                {"id": "4", "name": "code-quality"},
                {"id": "5", "name": "code-integration"},
                {"id": "6", "name": "implementation"},
                {"id": "7", "name": "non-english"},
                {"id": "8", "name": "outside-scope"},
            ],
            "labels": {
                "doc-a": {"tagIds": ["1", "2", "3", "4", "5", "6"]},
                "doc-b": {"tagIds": ["7", "8"]},
            },
        }

        processed = build_processed_export(data, source_name="sample.json")

        tag_names = [tag["name"] for tag in processed["tags"]]
        self.assertEqual(
            tag_names,
            [
                "Code Generation",
                "Documentation",
                "Software Design",
                "Software Testing",
                "filter",
                "instructive",
            ],
        )
        self.assertEqual(processed["dataset"]["sourceFile"], "sample.json")
        self.assertEqual(
            processed["processing"]["counts"]["documents_with_multiple_filter_sources"],
            1,
        )
        self.assertEqual(
            processed["processing"]["filter_source_document_counts"],
            {"agent-skill": 0, "outside-scope": 1, "wrong-language": 1},
        )

        doc_a_ids = processed["labels"]["doc-a"]["tagIds"]
        doc_b_ids = processed["labels"]["doc-b"]["tagIds"]
        self.assertEqual(len(doc_a_ids), 5)
        self.assertEqual(len(doc_b_ids), 1)

    def test_analyze_helpers_split_filtered_and_build_matrix(self):
        doc_labels = {
            "doc-a": {"commands", "Code Generation"},
            "doc-b": {"filter"},
            "doc-c": {"descriptive", "Software Design"},
        }

        retained, filtered = split_filtered_docs(doc_labels)

        self.assertEqual(set(retained), {"doc-a", "doc-c"})
        self.assertEqual(set(filtered), {"doc-b"})

        matrix = instruction_sdlc_matrix(retained)
        self.assertEqual(matrix["commands"]["Code Generation"], 1)
        self.assertEqual(matrix["descriptive"]["Software Design"], 1)


if __name__ == "__main__":
    unittest.main()
